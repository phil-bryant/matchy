from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError, as_completed
from contextlib import nullcontext
from datetime import timedelta
import hashlib
import logging
import os
import re
from time import monotonic, perf_counter
import requests
from sqlalchemy import text

from .ai_ranker import AiRanker, PROMPT_VERSION
from .cldr_cache import CldrCurrenciesCache
from .mailcart_client import MailcartClient
from .models import EmailCandidate
from .repository import MatchRepository
from .scoring import rank_candidates
from .settings import Settings

LOGGER = logging.getLogger(__name__)

#R020: Statuses that represent a completed AI evaluation; only these are cache-eligible. `failed`
#R020: runs are NOT in this set so transient errors (Mailcart down, Anthropic 404, etc.) self-heal
#R020: on the next loop instead of being permanently cached as no-ops.
_CACHE_HIT_STATUSES = frozenset({"succeeded", "needs_review", "no_candidates"})


def _runtime_profile_enabled() -> bool:
    enabled = os.environ.get("MATCHY_RUNTIME_PROFILE", "false").strip().lower() == "true"
    return enabled


def _runtime_profile_log(phase: str, details: str = "") -> None:
    if _runtime_profile_enabled():
        suffix = f" | {details}" if details else ""
        print(f"[matchy-runtime] {phase}{suffix}", flush=True)


class MatchService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._repository = MatchRepository(settings)
        self._mailcart_client = MailcartClient(settings)
        self._ai_ranker = AiRanker(settings)
        self._cldr_currency_matcher = CldrCurrenciesCache(settings).currency_matcher()
        cooldown_seconds = int(getattr(settings, "mailcart_failure_cooldown_seconds", 15) or 15)
        if cooldown_seconds < 0:
            cooldown_seconds = 0
        self._mailcart_failure_cooldown_seconds = cooldown_seconds
        self._mailcart_unavailable_until_monotonic = 0.0

    #R001: Raise a ValueError when a requested transaction cannot be loaded.
    #R020: Run the Mailcart search up-front and skip the AI call when nothing meaningful has changed
    #R020: since the previous run (same candidate id set under the same model + prompt version). This
    #R020: keeps the matchy auto-driver's per-loop cost bounded to a single Mailcart search per
    #R020: transaction instead of also paying for per-candidate body fetches and a Claude/GPT call.
    def match_transaction(self, transaction_id: str, trigger_source: str = "manual", force_rematch: bool = False) -> dict:
        with self._repository.session() as session:
            txn = self._repository.load_transaction(session, transaction_id)
            if txn is None:
                raise ValueError(f"Unknown transaction_id: {transaction_id}")
            candidates = self._search_candidates(txn, transaction_id)
            candidates = self._enrich_candidate_bodies(candidates, transaction_id=transaction_id)
            candidates = self._filter_currency_candidates(candidates)
            planned_model = self._ai_ranker.planned_model_name()
            current_hash = self._candidate_set_hash([c.message_id for c in candidates])
            cached_response = self._maybe_cached_response(
                session=session,
                transaction_id=transaction_id,
                candidates=candidates,
                planned_model=planned_model,
                current_hash=current_hash,
                force_rematch=force_rematch,
            )
            if cached_response is not None:
                return cached_response
            run_id = self._repository.create_run(
                session=session,
                transaction_id=transaction_id,
                trigger_source=trigger_source,
                model_name=planned_model,
                prompt_version=PROMPT_VERSION,
            )
            try:
                transaction_scope = session.begin_nested() if hasattr(session, "begin_nested") else nullcontext()
                with transaction_scope:
                    active_ids = set(
                        row["email_message_id"]
                        for row in session.execute(
                            text(
                                """
                                SELECT email_message_id
                                  FROM teller.transaction_email_match
                                 WHERE active = TRUE
                                   AND email_message_id IS NOT NULL
                                   AND transaction_id <> :transaction_id
                                """
                            ),
                            {"transaction_id": transaction_id},
                        ).mappings().all()
                    )
                    ranked = rank_candidates(txn, candidates, already_matched_ids=active_ids)
                    ai_selection = self._ai_ranker.select(txn, ranked)
                    self._repository.update_run_model_name(session=session, run_id=run_id, model_name=ai_selection.model_name)
                    self._repository.insert_candidates(
                        session=session,
                        match_run_id=run_id,
                        transaction_id=transaction_id,
                        candidates=ranked,
                        ai_selected_ids=set(ai_selection.selected_message_ids),
                    )
                    selected_ids = self._repository.persist_ai_result(
                        session=session,
                        transaction_id=transaction_id,
                        run_id=run_id,
                        ranked_candidates=ranked,
                        ai_selection=ai_selection,
                        auto_confirm_threshold=self._settings.auto_confirm_threshold,
                    )
            except Exception as exc:
                self._repository.mark_run_failed(session, run_id, str(exc))
                raise
        return {
            "transaction_id": transaction_id,
            "run_id": run_id,
            "selected_message_ids": selected_ids,
            "candidate_count": len(candidates),
            "ai_confidence": ai_selection.confidence,
            "uncertain": ai_selection.uncertain,
            "skipped": False,
        }

    #R020: Execute the scoped retrieval fallback chain (terms+date → terms-only → broad-term → empty)
    #R020: without yet creating a match_run row. Query-tier requests intentionally use scoped
    #R020: Mailcart syntax (`subject:`/`body:` plus optional `from:`/`to:` date bounds) and union
    #R020: results across terms to improve recall while preserving deterministic ordering.
    def _search_candidates(self, txn, transaction_id: str) -> list[EmailCandidate]:
        if self._mailcart_in_cooldown(transaction_id=transaction_id):
            return []
        terms = self._extract_search_terms(txn.description, txn.counterparty_name)
        #R040: Each mailcart search is a ~15-20s full-mailbox Graph scan, and the driver already runs
        #R040: several transactions in parallel, so we must keep per-transaction load to ~one scan.
        #R040: Issue queries one at a time and stop at the first that returns anything (early-stop):
        #R040: body matching leads because the merchant name reliably appears in receipt/confirmation
        #R040: bodies, so the most distinctive term's body query usually catches the right email on the
        #R040: first request. Subject, a window-free retry, and the historical recency fallback only run
        #R040: when earlier queries come back empty. We deliberately do NOT fan out concurrently —
        #R040: parallel scans saturate the single mailcart instance and push every request past its
        #R040: timeout.
        query_plan = (
            self._build_scoped_queries(terms, txn.date, fields=("body",), include_date_window=True)
            + self._build_scoped_queries(terms, txn.date, fields=("subject",), include_date_window=True)
            + self._build_scoped_queries(terms, txn.date, fields=("body",), include_date_window=False)
            + [""]
        )
        for query in query_plan:
            rows = self._search_mailcart(query=query, transaction_id=transaction_id, limit=75)
            candidates = self._dedupe_candidates(rows, limit=75)
            if candidates:
                return candidates
            if self._mailcart_in_cooldown(transaction_id=transaction_id):
                return []
        return []

    #R040: De-duplicate a single search result by message_id while preserving order and dropping rows
    #R040: without an id, capped at `limit`.
    @staticmethod
    def _dedupe_candidates(rows: list[EmailCandidate], limit: int) -> list[EmailCandidate]:
        deduped: dict[str, EmailCandidate] = {}
        for candidate in rows:
            message_id = str(candidate.message_id)
            if not message_id or message_id in deduped:
                continue
            deduped[message_id] = candidate
            if len(deduped) >= limit:
                break
        return list(deduped.values())

    #R040: A slow search (Timeout) means Mailcart is up but busy, not down: skip just that query and
    #R040: let the caller fall through to the next tier / the recency fallback. Only connection-level
    #R040: failures and 5xx responses arm the shared cooldown. Client errors (4xx) are real bugs and
    #R040: propagate so they are not silently masked.
    def _search_mailcart(self, query: str, transaction_id: str, limit: int) -> list[EmailCandidate]:
        try:
            return self._mailcart_client.search_candidates(query=query, limit=limit)
        except requests.exceptions.Timeout as exc:
            LOGGER.warning("mailcart search timed out query=%r transaction_id=%s error=%s", query, transaction_id, exc)
            return []
        except Exception as exc:
            LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", query, transaction_id, exc)
            if self._is_transient_mailcart_error(exc):
                self._mark_mailcart_temporarily_unavailable(transaction_id=transaction_id)
                return []
            raise

    def _mailcart_in_cooldown(self, transaction_id: str) -> bool:
        now = monotonic()
        unavailable_until = float(getattr(self, "_mailcart_unavailable_until_monotonic", 0.0) or 0.0)
        if now < unavailable_until:
            remaining_seconds = unavailable_until - now
            _runtime_profile_log(
                "mailcart-search-skipped-cooldown",
                f"transaction_id={transaction_id} remaining_seconds={remaining_seconds:0.1f}",
            )
            return True
        return False

    def _is_transient_mailcart_error(self, exc: Exception) -> bool:
        if isinstance(exc, requests.exceptions.ConnectionError):
            return True
        if isinstance(exc, requests.exceptions.HTTPError):
            response = getattr(exc, "response", None)
            status_code = int(getattr(response, "status_code", 0) or 0)
            return status_code >= 500
        if isinstance(exc, requests.exceptions.RequestException):
            response = getattr(exc, "response", None)
            status_code = int(getattr(response, "status_code", 0) or 0)
            return status_code >= 500
        return False

    def _mark_mailcart_temporarily_unavailable(self, transaction_id: str) -> None:
        cooldown_seconds = int(getattr(self, "_mailcart_failure_cooldown_seconds", 15) or 15)
        if cooldown_seconds > 0:
            next_available = monotonic() + cooldown_seconds
            self._mailcart_unavailable_until_monotonic = next_available
            _runtime_profile_log(
                "mailcart-search-cooldown-started",
                f"transaction_id={transaction_id} cooldown_seconds={cooldown_seconds}",
            )

    #R020: Decide whether the previous AI verdict still applies. Returns a cached response dict (the
    #R020: same shape as a fresh evaluation, with `skipped=True`) when all of these hold:
    #R020:   - a prior run exists,
    #R020:   - its status was a real completed evaluation (`_CACHE_HIT_STATUSES`),
    #R020:   - its model_name matches what the current ranker would use,
    #R020:   - its prompt_version matches the current `PROMPT_VERSION`, and
    #R020:   - its candidate id set is byte-identical (after sorting) to the current search result.
    #R020: Returns None to indicate the caller should fall through to the full AI pipeline.
    #R020: force_rematch bypasses the prompt_version (v2/v3) cache so new prompts take effect immediately.
    def _maybe_cached_response(
        self,
        session,
        transaction_id: str,
        candidates: list[EmailCandidate],
        planned_model: str,
        current_hash: str,
        force_rematch: bool = False,
    ) -> dict | None:
        if force_rematch:
            return None
        last_summary = self._repository.read_last_run_summary(session, transaction_id)
        if last_summary is None:
            return None
        if last_summary["status"] not in _CACHE_HIT_STATUSES:
            return None
        if last_summary["model_name"] != planned_model:
            return None
        if last_summary["prompt_version"] != PROMPT_VERSION:
            return None
        cached_hash = self._candidate_set_hash(last_summary["candidate_message_ids"])
        if cached_hash != current_hash:
            return None
        active = self._repository.read_active_match_summary(session, transaction_id) or {}
        if active.get("state") == "ai_no_match_found":
            return None
        selected_ids: list[str] = []
        active_email_id = active.get("email_message_id")
        if active_email_id and active.get("state") != "ai_no_match_found":
            selected_ids = [str(active_email_id)]
        LOGGER.info(
            "matchy cache hit transaction_id=%s last_run_id=%s candidates=%d model=%s prompt=%s",
            transaction_id,
            last_summary["match_run_id"],
            len(candidates),
            planned_model,
            PROMPT_VERSION,
        )
        return {
            "transaction_id": transaction_id,
            "run_id": last_summary["match_run_id"],
            "selected_message_ids": selected_ids,
            "candidate_count": len(candidates),
            "ai_confidence": active.get("ai_confidence") if active else None,
            "uncertain": None,
            "skipped": True,
            "skip_reason": "candidate_set_unchanged_for_model_and_prompt",
            "state": active.get("state") if active else None,
        }

    #R020: Deterministic, order-independent fingerprint of the candidate id set. We sort first so a
    #R020: shuffled order from Mailcart doesn't masquerade as a real change.
    @staticmethod
    def _candidate_set_hash(message_ids: list[str]) -> str:
        digest = hashlib.sha256()
        for message_id in sorted(str(item) for item in message_ids):
            digest.update(message_id.encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()

    #R010: Discover pending transactions and run each through match_transaction with the caller-specified
    #R010: trigger source.
    #R025: A single transaction's failure (e.g., transient Anthropic 429, Mailcart blip) must NOT abort
    #R025: the rest of the batch — each error is captured into the result row, mark_run_failed has
    #R025: already recorded the failure in the DB, and the next driver loop will retry that transaction.
    #R030: Process pending transactions concurrently while preserving deterministic output order.
    def match_pending_transactions(self, limit: int = 100, lookback_days: int = 14, trigger_source: str = "auto", force_rematch: bool = False) -> list[dict]:
        batch_started_at = perf_counter()
        with self._repository.session() as session:
            transaction_ids = self._repository.list_pending_transaction_ids(
                session=session,
                limit=limit,
                lookback_days=lookback_days,
            )
        max_workers_raw = os.environ.get("MATCHY_PENDING_MAX_WORKERS", "4").strip()
        max_workers = 4
        try:
            parsed_workers = int(max_workers_raw)
            if parsed_workers >= 1:
                max_workers = parsed_workers
        except ValueError:
            max_workers = 4
        if transaction_ids:
            max_workers = min(max_workers, len(transaction_ids))
        if max_workers < 1:
            max_workers = 1
        _runtime_profile_log(
            "pending-batch-start",
            (
                f"count={len(transaction_ids)} limit={limit} lookback_days={lookback_days} "
                f"trigger_source={trigger_source} workers={max_workers}"
            ),
        )
        results: list[dict] = [{} for _ in transaction_ids]
        if transaction_ids:
            run_started_by_index: dict[int, float] = {}
            future_to_index: dict[Future, int] = {}
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                index = 0
                while index < len(transaction_ids):
                    transaction_id = transaction_ids[index]
                    run_started_by_index[index] = perf_counter()
                    future = executor.submit(self.match_transaction, transaction_id=transaction_id, trigger_source=trigger_source, force_rematch=force_rematch)
                    future_to_index[future] = index
                    index += 1
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    transaction_id = transaction_ids[index]
                    run_elapsed_seconds = perf_counter() - run_started_by_index[index]
                    try:
                        results[index] = future.result()
                        _runtime_profile_log(
                            "pending-txn-complete",
                            f"transaction_id={transaction_id} status=ok elapsed={run_elapsed_seconds:0.3f}s",
                        )
                    except Exception as exc:
                        LOGGER.warning(
                            "matchy batch entry failed transaction_id=%s error=%s",
                            transaction_id, exc,
                        )
                        _runtime_profile_log(
                            "pending-txn-complete",
                            f"transaction_id={transaction_id} status=error elapsed={run_elapsed_seconds:0.3f}s",
                        )
                        results[index] = {
                            "transaction_id": transaction_id,
                            "run_id": None,
                            "selected_message_ids": [],
                            "candidate_count": 0,
                            "ai_confidence": 0.0,
                            "uncertain": True,
                            "skipped": False,
                            "error": str(exc),
                        }
        _runtime_profile_log(
            "pending-batch-complete",
            f"count={len(transaction_ids)} elapsed={perf_counter() - batch_started_at:0.3f}s",
        )
        return results

    #R015: Replace each candidate's body_text with the full email body fetched from Mailcart so that
    #R015: amount/keyword/compact-merchant hints can score against the real message body. Returns the
    #R015: original candidates unchanged when the feature flag is off or when the client is missing
    #R015: get_message (older Mailcart deployments). Per-candidate failures fall through to the
    #R015: original candidate so a flaky message id does not poison the whole run.
    def _enrich_candidate_bodies(self, candidates: list[EmailCandidate], transaction_id: str) -> list[EmailCandidate]:
        if not candidates:
            return candidates
        if not getattr(self._settings, "mailcart_body_enrichment_enabled", False):
            return candidates
        get_message = getattr(self._mailcart_client, "get_message", None)
        if not callable(get_message):
            return candidates
        limit = int(getattr(self._settings, "mailcart_body_enrichment_limit", 75) or 75)
        timeout_seconds = int(getattr(self._settings, "mailcart_body_enrichment_timeout_seconds", 25) or 25)
        max_workers = int(getattr(self._settings, "mailcart_body_enrichment_max_workers", 8) or 8)
        per_message_timeout = int(getattr(self._settings, "mailcart_get_message_timeout_seconds", 6) or 6)
        if max_workers < 1:
            max_workers = 1
        if timeout_seconds < 1:
            timeout_seconds = 1
        if per_message_timeout < 1:
            per_message_timeout = 1
        enrich_count = min(len(candidates), limit)
        if enrich_count < 1:
            return candidates
        payloads: dict[int, dict] = {}
        message_id_to_first_index: dict[str, int] = {}
        for index in range(enrich_count):
            message_id = str(candidates[index].message_id)
            if message_id not in message_id_to_first_index:
                message_id_to_first_index[message_id] = index
        message_payload_by_id: dict[str, dict] = {}
        unique_fetch_count = len(message_id_to_first_index)
        future_to_message_id: dict[Future, str] = {}
        with ThreadPoolExecutor(max_workers=min(max_workers, unique_fetch_count)) as executor:
            for message_id in message_id_to_first_index:
                future = executor.submit(get_message, message_id, per_message_timeout)
                future_to_message_id[future] = message_id
            unresolved_count = 0
            try:
                for future in as_completed(future_to_message_id, timeout=timeout_seconds):
                    message_id = future_to_message_id[future]
                    try:
                        payload = future.result() or {}
                        message_payload_by_id[message_id] = payload
                    except Exception as exc:
                        LOGGER.warning(
                            "mailcart get_message failed message_id=%s transaction_id=%s error=%s",
                            message_id, transaction_id, exc,
                        )
            except TimeoutError:
                unresolved_count = len([future for future in future_to_message_id if not future.done()])
                LOGGER.warning(
                    "mailcart body enrichment timed out transaction_id=%s unresolved_candidates=%s timeout_seconds=%s",
                    transaction_id,
                    unresolved_count,
                    timeout_seconds,
                )
        for index in range(enrich_count):
            message_id = str(candidates[index].message_id)
            if message_id in message_payload_by_id:
                payloads[index] = message_payload_by_id[message_id]
        enriched: list[EmailCandidate] = []
        for index in range(enrich_count):
            candidate = candidates[index]
            if index not in payloads:
                enriched.append(candidate)
                continue
            payload = payloads[index]
            body_text = (
                str(payload.get("text_body") or "").strip()
                or str(payload.get("html_body") or "").strip()
                or str(payload.get("body_text") or "").strip()
            )
            if not body_text:
                enriched.append(candidate)
                continue
            enriched.append(EmailCandidate(
                message_id=candidate.message_id,
                subject=candidate.subject or str(payload.get("subject") or ""),
                preview=candidate.preview or str(payload.get("preview") or ""),
                received_at=candidate.received_at,
                sender=candidate.sender or str(payload.get("sender") or ""),
                body_text=body_text,
            ))
        if len(candidates) > enrich_count:
            enriched.extend(candidates[enrich_count:])
        return enriched

    #R050: Scope matchable candidates to messages containing a standalone CLDR currency code or symbol.
    def _filter_currency_candidates(self, candidates: list[EmailCandidate]) -> list[EmailCandidate]:
        filtered = candidates
        matcher = getattr(self, "_cldr_currency_matcher", None)
        if candidates and matcher is not None and getattr(matcher, "tokens", frozenset()):
            filtered = []
            for candidate in candidates:
                text_blob = f"{candidate.subject} {candidate.preview} {candidate.body_text}"
                if matcher.contains_standalone_currency(text_blob):
                    filtered.append(candidate)
        return filtered

    #R005: Build deterministic scoped search terms from merchant + transaction text. Capped at two
    #R005: terms because each emitted query is a slow full-mailbox scan; the two most distinctive
    #R005: merchant tokens (counterparty first, then description) carry almost all of the signal.
    _MAX_SEARCH_TERMS = 2

    def _extract_search_terms(self, description: str, counterparty_name: str) -> list[str]:
        ordered_tokens: list[str] = []
        seen: set[str] = set()
        sources = [counterparty_name or "", description or ""]
        for source in sources:
            normalized = re.sub(r"[^a-z0-9\s]", " ", source.lower())
            for token in normalized.split():
                if len(token) < 4:
                    continue
                if token.isdigit():
                    continue
                if re.search(r"[a-z]", token) is None:
                    continue
                if token in seen:
                    continue
                seen.add(token)
                ordered_tokens.append(token)
                if len(ordered_tokens) >= self._MAX_SEARCH_TERMS:
                    return ordered_tokens
        return ordered_tokens

    def _build_scoped_queries(
        self,
        terms: list[str],
        txn_date,
        fields: tuple[str, ...] = ("body",),
        include_date_window: bool = True,
    ) -> list[str]:
        if not terms:
            return []
        date_window = self._date_window_suffix(txn_date) if include_date_window else ""
        scoped_queries: list[str] = []
        for term in terms:
            for field in fields:
                scoped_queries.append(f"{field}:{term}{date_window}")
        return scoped_queries

    def _date_window_suffix(self, txn_date) -> str:
        window_days = int(getattr(self._settings, "mailcart_search_date_window_days", 45) or 45)
        if window_days <= 0:
            return ""
        from_date = (txn_date - timedelta(days=window_days)).date().isoformat()
        to_date = (txn_date + timedelta(days=window_days)).date().isoformat()
        return f" from:{from_date} to:{to_date}"

    def confirm_match(self, transaction_id: str, email_message_id: str, note: str | None = None) -> dict:
        #R045: Human confirm: deactivate prior active match for txn, insert human_confirmed state.
        # This prevents the state transition conflict error by properly managing active flags.
        with self._repository.session() as session:
            self._repository.deactivate_active_match(session, transaction_id)
            self._repository.insert_human_confirmed_match(
                session, transaction_id, email_message_id, note
            )
        return {"status": "confirmed", "match_id": None}
