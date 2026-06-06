from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import nullcontext
import logging
import os
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .ai_ranker import AiRanker, PROMPT_VERSION
from .caching import CachingMixin
from .cldr_cache import CldrCurrenciesCache
from .email_move import EmailMoveMixin
from .enrichment import EnrichmentMixin
from .mailcart_client import MailcartClient
from .near_duplicate import NearDuplicateMixin
from .repository import MatchRepository
from .runtime_profile import _runtime_profile_log
from .scoring import rank_candidates
from .search import SearchMixin
from .settings import Settings

LOGGER = logging.getLogger(__name__)


class MatchService(SearchMixin, EnrichmentMixin, NearDuplicateMixin, CachingMixin, EmailMoveMixin):
    #R310: Run Mailcart startup preflight exactly once during initialization when enabled.
    def __init__(self, settings: Settings):
        self._settings = settings
        self._repository = MatchRepository(settings)
        self._mailcart_client = MailcartClient(settings)
        if bool(getattr(settings, "mailcart_startup_healthcheck_enabled", True)):
            self._mailcart_client.startup_preflight_healthcheck()
        self._ai_ranker = AiRanker(settings)
        self._cldr_currency_matcher = CldrCurrenciesCache(settings).currency_matcher()
        cooldown_seconds = int(getattr(settings, "mailcart_failure_cooldown_seconds", 15) or 15)
        if cooldown_seconds < 0:
            cooldown_seconds = 0
        self._mailcart_failure_cooldown_seconds = cooldown_seconds
        self._mailcart_unavailable_until_monotonic = 0.0

    #R001: Raise a ValueError when a requested transaction cannot be loaded.
    # Orchestration: search up-front, enrich/filter/collapse candidates, consult the Postgres-backed
    # AI-skip cache (R020, see caching.py), then run the AI pipeline and persist results.
    def match_transaction(
        self,
        transaction_id: str,
        trigger_source: str = "manual",
        force_rematch: bool = False,
        *,
        session=None,
        record_failure: bool = True,
    ) -> dict:
        def _session_scope():
            return nullcontext(session) if session is not None else self._repository.session()

        with _session_scope() as active_session:
            txn = self._repository.load_transaction(active_session, transaction_id)
            if txn is None:
                raise ValueError(f"Unknown transaction_id: {transaction_id}")
        candidates = self._search_candidates(txn, transaction_id)
        candidates = self._enrich_candidate_bodies(candidates, transaction_id=transaction_id)
        candidates = self._filter_currency_candidates(candidates)
        # Collapse near-duplicate receipts after enrichment so similarity is judged on full bodies (R055).
        candidates = self._collapse_near_duplicates(candidates, self._near_duplicate_max_distance())
        planned_model = self._ai_ranker.planned_model_name()
        with _session_scope() as active_session:
            active_ids = self._active_ids_for_other_transactions(session=active_session, transaction_id=transaction_id)
        ranked = rank_candidates(txn, candidates, already_matched_ids=active_ids)
        current_rows = self._ranked_candidate_cache_rows(ranked)
        current_hash = self._candidate_set_hash(current_rows)
        current_message_id_hash = self._candidate_message_id_hash([row["email_message_id"] for row in current_rows])
        run_id: int | None = None
        with _session_scope() as active_session:
            cached_response = self._maybe_cached_response(
                session=active_session,
                transaction_id=transaction_id,
                candidates=candidates,
                planned_model=planned_model,
                current_hash=current_hash,
                current_message_id_hash=current_message_id_hash,
                force_rematch=force_rematch,
            )
            if cached_response is not None:
                return cached_response
            run_id = self._repository.create_run(
                session=active_session,
                transaction_id=transaction_id,
                trigger_source=trigger_source,
                model_name=planned_model,
                prompt_version=PROMPT_VERSION,
            )
        try:
            ai_selection = self._ai_ranker.select(txn, ranked)
            with _session_scope() as active_session:
                transaction_scope = active_session.begin_nested() if hasattr(active_session, "begin_nested") else nullcontext()
                with transaction_scope:
                    self._repository.update_run_model_name(session=active_session, run_id=run_id, model_name=ai_selection.model_name)
                    self._repository.insert_candidates(
                        session=active_session,
                        match_run_id=run_id,
                        transaction_id=transaction_id,
                        candidates=ranked,
                        ai_selected_ids=set(ai_selection.selected_message_ids),
                    )
                    selected_ids = self._repository.persist_ai_result(
                        session=active_session,
                        transaction_id=transaction_id,
                        run_id=run_id,
                        ranked_candidates=ranked,
                        ai_selection=ai_selection,
                        auto_confirm_threshold=self._settings.auto_confirm_threshold,
                    )
            self._maybe_move_selected_messages(selected_ids, transaction_id=transaction_id, source="ai")
        except Exception as exc:
            if record_failure and run_id is not None:
                try:
                    if session is None:
                        with self._repository.session() as failed_session:
                            self._repository.mark_run_failed(failed_session, run_id, str(exc))
                    else:
                        self._repository.mark_run_failed(session, run_id, str(exc))
                except Exception as mark_exc:
                    LOGGER.warning("matchy failed to persist failed run run_id=%s error=%s", run_id, mark_exc)
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

    #R300: Commit the shared repository unit-of-work once after a fully successful atomic batch.
    #R305: Roll back the shared session and re-raise when any atomic batch entry fails.
    def match_transactions_atomic(
        self,
        transaction_ids: list[str],
        trigger_source: str = "manual",
        force_rematch: bool = False,
    ) -> list[dict]:
        rows: list[dict] = []
        with self._repository.session() as session:
            for transaction_id in transaction_ids:
                rows.append(
                    self.match_transaction(
                        transaction_id=transaction_id,
                        trigger_source=trigger_source,
                        force_rematch=force_rematch,
                        session=session,
                        record_failure=False,
                    )
                )
        return rows

    def _active_ids_for_other_transactions(self, session, transaction_id: str) -> set[str]:
        repository_reader = getattr(self._repository, "list_active_email_ids_for_other_transactions", None)
        if callable(repository_reader):
            return set(repository_reader(session=session, transaction_id=transaction_id))
        if not hasattr(session, "execute"):
            return set()
        return set(
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

    def confirm_match(self, transaction_id: str, email_message_id: str, note: str | None = None) -> dict:
        #R045: Human confirm: deactivate prior active match for txn, insert human_confirmed_ai_match state.
        # This prevents the state transition conflict error by properly managing active flags.
        # Unknown transaction/email ids violate the foreign keys; surface that as a domain error
        # (HTTP 404 at the API) instead of leaking a 500 on client-supplied ids.
        match_id = None
        try:
            with self._repository.session() as session:
                self._repository.deactivate_active_match(session, transaction_id)
                match_id = self._repository.insert_human_confirmed_match(
                    session, transaction_id, email_message_id, note
                )
        except IntegrityError as exc:
            raise ValueError(
                f"Unknown transaction_id or email_message_id for confirmation: {transaction_id}/{email_message_id}"
            ) from exc
        self._maybe_move_selected_messages([email_message_id], transaction_id=transaction_id, source="human_confirm")
        return {"status": "confirmed", "match_id": match_id}
