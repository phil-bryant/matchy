from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError, as_completed
from contextlib import nullcontext
import hashlib
import logging
import os
import re
from time import monotonic, perf_counter
from sqlalchemy import text

from .ai_ranker import AiRanker, PROMPT_VERSION
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
    def match_transaction(self, transaction_id: str, trigger_source: str = "manual") -> dict:
        with self._repository.session() as session:
            txn = self._repository.load_transaction(session, transaction_id)
            if txn is None:
                raise ValueError(f"Unknown transaction_id: {transaction_id}")
            candidates = self._search_candidates(txn, transaction_id)
            planned_model = self._ai_ranker.planned_model_name()
            current_hash = self._candidate_set_hash([c.message_id for c in candidates])
            cached_response = self._maybe_cached_response(
                session=session,
                transaction_id=transaction_id,
                candidates=candidates,
                planned_model=planned_model,
                current_hash=current_hash,
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
                    candidates = self._enrich_candidate_bodies(candidates, transaction_id=transaction_id)
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

    #R020: Execute the existing 4-step search fallback chain (specific → broad → doordash → empty)
    #R020: without yet creating a match_run row. Mailcart search errors are swallowed so a transient
    #R020: Mailcart blip still allows the cache check to decide whether the last run's verdict stands.
    def _search_candidates(self, txn, transaction_id: str) -> list[EmailCandidate]:
        now = monotonic()
        unavailable_until = float(getattr(self, "_mailcart_unavailable_until_monotonic", 0.0) or 0.0)
        if now < unavailable_until:
            remaining_seconds = unavailable_until - now
            _runtime_profile_log(
                "mailcart-search-skipped-cooldown",
                f"transaction_id={transaction_id} remaining_seconds={remaining_seconds:0.1f}",
            )
            return []
        query = self._build_query(txn.description, txn.counterparty_name)
        candidates: list[EmailCandidate] = []
        try:
            candidates = self._mailcart_client.search_candidates(query=query, limit=75)
        except Exception as exc:
            LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", query, transaction_id, exc)
            self._mark_mailcart_temporarily_unavailable(transaction_id=transaction_id)
            candidates = []
        if not candidates:
            broad_query = self._build_broad_query(txn.description, txn.counterparty_name)
            try:
                candidates = self._mailcart_client.search_candidates(query=broad_query, limit=75)
            except Exception as exc:
                LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", broad_query, transaction_id, exc)
                self._mark_mailcart_temporarily_unavailable(transaction_id=transaction_id)
                candidates = []
        if not candidates and "doordash" in (txn.description or "").lower():
            try:
                candidates = self._mailcart_client.search_candidates(query="doordash", limit=75)
            except Exception as exc:
                LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", "doordash", transaction_id, exc)
                self._mark_mailcart_temporarily_unavailable(transaction_id=transaction_id)
                candidates = []
        if not candidates:
            try:
                candidates = self._mailcart_client.search_candidates(query="", limit=75)
            except Exception as exc:
                LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", "", transaction_id, exc)
                self._mark_mailcart_temporarily_unavailable(transaction_id=transaction_id)
                candidates = []
        return candidates

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
    def _maybe_cached_response(
        self,
        session,
        transaction_id: str,
        candidates: list[EmailCandidate],
        planned_model: str,
        current_hash: str,
    ) -> dict | None:
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
    def match_pending_transactions(self, limit: int = 100, lookback_days: int = 14, trigger_source: str = "auto") -> list[dict]:
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
                    future = executor.submit(self.match_transaction, transaction_id=transaction_id, trigger_source=trigger_source)
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

    #R005: Build search queries from normalized, non-numeric tokens with deterministic truncation.
    def _build_query(self, description: str, counterparty_name: str) -> str:
        raw = f"{counterparty_name} {description}".lower()
        normalized = re.sub(r"[^a-z0-9\s]", " ", raw)
        tokens = [token for token in normalized.split(" ") if len(token) >= 4 and not token.isdigit()]
        if not tokens:
            return ""
        return " ".join(tokens[:3])

    def _build_broad_query(self, description: str, counterparty_name: str) -> str:
        raw = f"{counterparty_name} {description}".lower()
        normalized = re.sub(r"[^a-z0-9\s]", " ", raw)
        tokens = [token for token in normalized.split(" ") if len(token) >= 4 and not token.isdigit()]
        specific_tokens = [token for token in tokens if token not in {"doordash", "doordashcom"}]
        if specific_tokens:
            return specific_tokens[0]
        if "doordash" in tokens:
            return "doordash"
        if tokens:
            return tokens[0]
        return ""
