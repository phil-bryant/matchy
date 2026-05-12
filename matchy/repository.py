from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .models import AiSelection, RankedCandidate, TransactionInput
from .settings import Settings


class MatchRepository:
    def __init__(self, settings: Settings):
        if not settings.teller_db_password:
            raise RuntimeError("TELLER_DB_PASSWORD is required for matchy writes")
        self._engine = create_engine(
            "postgresql+psycopg2://",
            connect_args={
                "host": settings.teller_db_host,
                "port": settings.teller_db_port,
                "dbname": settings.teller_db_name,
                "user": settings.teller_db_user,
                "password": settings.teller_db_password,
            },
        )
        self._session_factory = sessionmaker(bind=self._engine)

    @contextmanager
    def session(self):
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def load_transaction(self, session, transaction_id: str) -> TransactionInput | None:
        row = session.execute(
            text(
                """
                SELECT tt.transaction_id,
                       tt.account_id,
                       tt.amount,
                       tt.date::timestamp AS date_ts,
                       tt.description,
                       COALESCE(tdc.name, '') AS counterparty_name
                  FROM teller.transaction tt
             LEFT JOIN teller.transaction_details td
                    ON td.transaction_details_id = tt.transaction_details_id
             LEFT JOIN teller.transaction_details_counterparty tdc
                    ON tdc.transaction_details_counterparty_id = td.counterparty_id
                 WHERE tt.transaction_id = :transaction_id
                 LIMIT 1
                """
            ),
            {"transaction_id": transaction_id},
        ).mappings().fetchone()
        if row is None:
            return None
        return TransactionInput(
            transaction_id=row["transaction_id"],
            account_id=row["account_id"],
            amount=Decimal(row["amount"]),
            date=row["date_ts"].replace(tzinfo=timezone.utc),
            description=row["description"],
            counterparty_name=row["counterparty_name"] or "",
        )

    def create_run(self, session, transaction_id: str, trigger_source: str, model_name: str, prompt_version: str) -> int:
        return int(
            session.execute(
                text(
                    """
                    INSERT INTO teller.transaction_email_match_run (
                        transaction_id, trigger_source, model_name, prompt_version, status
                    ) VALUES (
                        :transaction_id, :trigger_source, :model_name, :prompt_version, 'needs_review'
                    )
                    RETURNING match_run_id
                    """
                ),
                {
                    "transaction_id": transaction_id,
                    "trigger_source": trigger_source,
                    "model_name": model_name,
                    "prompt_version": prompt_version,
                },
            ).scalar_one()
        )

    def insert_candidates(self, session, match_run_id: int, transaction_id: str, candidates: list[RankedCandidate], ai_selected_ids: set[str]) -> None:
        for ranked in candidates:
            session.execute(
                text(
                    """
                    INSERT INTO teller.transaction_email_candidate (
                        match_run_id,
                        transaction_id,
                        email_message_id,
                        email_received_at,
                        score,
                        reason_json,
                        is_unmatched_email_priority,
                        is_selected_by_ai
                    ) VALUES (
                        :match_run_id,
                        :transaction_id,
                        :email_message_id,
                        :email_received_at,
                        :score,
                        CAST(:reason_json AS jsonb),
                        :is_unmatched_email_priority,
                        :is_selected_by_ai
                    )
                    """
                ),
                {
                    "match_run_id": match_run_id,
                    "transaction_id": transaction_id,
                    "email_message_id": ranked.candidate.message_id,
                    "email_received_at": ranked.candidate.received_at,
                    "score": ranked.score,
                    "reason_json": __import__("json").dumps(ranked.reasons),
                    "is_unmatched_email_priority": ranked.reasons.get("unmatched_email_priority", False),
                    "is_selected_by_ai": ranked.candidate.message_id in ai_selected_ids,
                },
            )

    def has_active_match(self, session, email_message_id: str) -> bool:
        return bool(
            session.execute(
                text(
                    """
                    SELECT 1
                      FROM teller.transaction_email_match
                     WHERE email_message_id = :email_message_id
                       AND active = TRUE
                     LIMIT 1
                    """
                ),
                {"email_message_id": email_message_id},
            ).fetchone()
        )

    def persist_ai_result(
        self,
        session,
        transaction_id: str,
        run_id: int,
        ranked_candidates: list[RankedCandidate],
        ai_selection: AiSelection,
        auto_confirm_threshold: float,
    ) -> list[str]:
        selected = []
        now = datetime.now(tz=timezone.utc)
        selected_ids = set(ai_selection.selected_message_ids)

        if not ranked_candidates or not selected_ids:
            session.execute(
                text(
                    """
                    INSERT INTO teller.transaction_email_match (
                        transaction_id,
                        email_message_id,
                        state,
                        ai_confidence,
                        explanation_json,
                        selected_by,
                        selected_at,
                        active
                    ) VALUES (
                        :transaction_id,
                        NULL,
                        'ai_no_match_found',
                        :ai_confidence,
                        CAST(:explanation_json AS jsonb),
                        'ai',
                        :selected_at,
                        TRUE
                    )
                    """
                ),
                {
                    "transaction_id": transaction_id,
                    "ai_confidence": ai_selection.confidence,
                    "explanation_json": __import__("json").dumps(
                        {"rationale": ai_selection.rationale, "run_id": run_id}
                    ),
                    "selected_at": now,
                },
            )
            self._update_run_status(session, run_id, "no_candidates")
            return selected

        state = "ai_candidate_uncertain"
        if ai_selection.confidence >= auto_confirm_threshold and not ai_selection.uncertain:
            state = "ai_match_confident"

        for ranked in ranked_candidates:
            if ranked.candidate.message_id not in selected_ids:
                continue
            if self.has_active_match(session, ranked.candidate.message_id):
                state = "ai_candidate_uncertain"
            session.execute(
                text(
                    """
                    INSERT INTO teller.transaction_email_match (
                        transaction_id,
                        email_message_id,
                        state,
                        ai_confidence,
                        explanation_json,
                        selected_by,
                        selected_at,
                        active
                    ) VALUES (
                        :transaction_id,
                        :email_message_id,
                        :state,
                        :ai_confidence,
                        CAST(:explanation_json AS jsonb),
                        'ai',
                        :selected_at,
                        TRUE
                    )
                    """
                ),
                {
                    "transaction_id": transaction_id,
                    "email_message_id": ranked.candidate.message_id,
                    "state": state,
                    "ai_confidence": ai_selection.confidence,
                    "explanation_json": __import__("json").dumps(
                        {
                            "rationale": ai_selection.rationale,
                            "deterministic_reasons": ranked.reasons,
                            "run_id": run_id,
                        }
                    ),
                    "selected_at": now,
                },
            )
            selected.append(ranked.candidate.message_id)

        self._update_run_status(session, run_id, "needs_review" if state == "ai_candidate_uncertain" else "succeeded")
        return selected

    def _update_run_status(self, session, run_id: int, status: str, error_text: str | None = None) -> None:
        session.execute(
            text(
                """
                UPDATE teller.transaction_email_match_run
                   SET status = :status,
                       completed_at = CURRENT_TIMESTAMP,
                       error_text = :error_text
                 WHERE match_run_id = :match_run_id
                """
            ),
            {"status": status, "error_text": error_text, "match_run_id": run_id},
        )

    def mark_run_failed(self, session, run_id: int, error_text: str) -> None:
        self._update_run_status(session, run_id, "failed", error_text=error_text)
