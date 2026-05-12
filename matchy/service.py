from __future__ import annotations

import re
from sqlalchemy import text

from .ai_ranker import AiRanker, PROMPT_VERSION
from .email_client import EmailClient
from .repository import MatchRepository
from .scoring import rank_candidates
from .settings import Settings


class MatchService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._repository = MatchRepository(settings)
        self._email_client = EmailClient(settings)
        self._ai_ranker = AiRanker(settings)

    def match_transaction(self, transaction_id: str, trigger_source: str = "manual") -> dict:
        with self._repository.session() as session:
            txn = self._repository.load_transaction(session, transaction_id)
            if txn is None:
                raise ValueError(f"Unknown transaction_id: {transaction_id}")
            run_id = self._repository.create_run(
                session=session,
                transaction_id=transaction_id,
                trigger_source=trigger_source,
                model_name=self._settings.openai_model,
                prompt_version=PROMPT_VERSION,
            )
            try:
                query = self._build_query(txn.description, txn.counterparty_name)
                candidates = self._email_client.search_candidates(query=query, limit=75)
                active_ids = set(
                    row["email_message_id"]
                    for row in session.execute(
                        text(
                            """
                            SELECT email_message_id
                              FROM teller.transaction_email_match
                             WHERE active = TRUE
                               AND email_message_id IS NOT NULL
                            """
                        )
                    ).mappings().all()
                )
                ranked = rank_candidates(txn, candidates, already_matched_ids=active_ids)
                ai_selection = self._ai_ranker.select(txn, ranked)
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

    def _build_query(self, description: str, counterparty_name: str) -> str:
        text = f"{description} {counterparty_name}".strip()
        compact = re.sub(r"\s+", " ", text)
        parts = compact.split(" ")
        return " ".join(parts[:8])
