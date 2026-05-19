from __future__ import annotations

import logging
import re
from sqlalchemy import text

from .ai_ranker import AiRanker, PROMPT_VERSION
from .mailcart_client import MailcartClient
from .repository import MatchRepository
from .scoring import rank_candidates
from .settings import Settings

LOGGER = logging.getLogger(__name__)


class MatchService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._repository = MatchRepository(settings)
        self._mailcart_client = MailcartClient(settings)
        self._ai_ranker = AiRanker(settings)

    #R001: Raise a ValueError when a requested transaction cannot be loaded.
    def match_transaction(self, transaction_id: str, trigger_source: str = "manual") -> dict:
        with self._repository.session() as session:
            txn = self._repository.load_transaction(session, transaction_id)
            if txn is None:
                raise ValueError(f"Unknown transaction_id: {transaction_id}")
            run_id = self._repository.create_run(
                session=session,
                transaction_id=transaction_id,
                trigger_source=trigger_source,
                model_name=self._ai_ranker.planned_model_name(),
                prompt_version=PROMPT_VERSION,
            )
            try:
                query = self._build_query(txn.description, txn.counterparty_name)
                candidates = []
                try:
                    candidates = self._mailcart_client.search_candidates(query=query, limit=75)
                except Exception as exc:
                    LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", query, transaction_id, exc)
                    candidates = []
                if not candidates:
                    broad_query = self._build_broad_query(txn.description, txn.counterparty_name)
                    try:
                        candidates = self._mailcart_client.search_candidates(query=broad_query, limit=75)
                    except Exception as exc:
                        LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", broad_query, transaction_id, exc)
                        candidates = []
                if not candidates and "doordash" in (txn.description or "").lower():
                    try:
                        candidates = self._mailcart_client.search_candidates(query="doordash", limit=75)
                    except Exception as exc:
                        LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", "doordash", transaction_id, exc)
                        candidates = []
                if not candidates:
                    try:
                        candidates = self._mailcart_client.search_candidates(query="", limit=75)
                    except Exception as exc:
                        LOGGER.warning("mailcart search failed query=%r transaction_id=%s error=%s", "", transaction_id, exc)
                        candidates = []
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
        }

    #R010: Discover pending transactions and run each through match_transaction with the caller-specified trigger source.
    def match_pending_transactions(self, limit: int = 100, lookback_days: int = 14, trigger_source: str = "auto") -> list[dict]:
        with self._repository.session() as session:
            transaction_ids = self._repository.list_pending_transaction_ids(
                session=session,
                limit=limit,
                lookback_days=lookback_days,
            )
        results: list[dict] = []
        for transaction_id in transaction_ids:
            results.append(self.match_transaction(transaction_id=transaction_id, trigger_source=trigger_source))
        return results

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
