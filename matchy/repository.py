from __future__ import annotations

from contextlib import contextmanager
from datetime import timezone
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .match_writer import MatchWriterMixin
from .models import TransactionInput
from .settings import Settings


class MatchRepository(MatchWriterMixin):
    #R001: Refuse repository initialization when Teller DB credentials are unavailable.
    def __init__(self, settings: Settings):
        if not settings.teller_db_password:
            raise RuntimeError("TELLER_DB_PASSWORD is required for matchy writes")
        self._write_enabled = bool(getattr(settings, "write_enabled", True))
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

    #R005: Commit successful unit-of-work sessions and rollback on failures.
    @contextmanager
    def session(self):
        session = self._session_factory()
        write_enabled = bool(getattr(self, "_write_enabled", True))
        try:
            yield session
            if write_enabled:
                session.commit()
            else:
                session.rollback()
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
                    ON tdc.transaction_details_counterparty_id = td.transaction_details_counterparty_id
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

    def update_run_model_name(self, session, run_id: int, model_name: str) -> None:
        session.execute(
            text(
                """
                UPDATE teller.transaction_email_match_run
                   SET model_name = :model_name
                 WHERE match_run_id = :match_run_id
                """
            ),
            {"model_name": model_name, "match_run_id": run_id},
        )

    #R010: Return deterministic pending transaction IDs for any transaction within the lookback window
    #R010: whose active match is not in a settled state. Settled = high-confidence AI match,
    #R010: human-confirmed match, human-overridden match, or human-marked no-email
    #R010: (state='ai_no_match_found' with selected_by='human'). Everything else — never matched,
    #R010: AI-only "no match found", or "candidate uncertain" — is re-queued so matchy retries it.
    def list_pending_transaction_ids(self, session, limit: int = 100, lookback_days: int = 14) -> list[str]:
        rows = session.execute(
            text(
                """
                WITH latest_runs AS (
                    SELECT DISTINCT ON (temr.transaction_id)
                           temr.transaction_id,
                           temr.created_at,
                           temr.completed_at
                      FROM teller.transaction_email_match_run temr
                     ORDER BY temr.transaction_id, temr.match_run_id DESC
                )
                SELECT tt.transaction_id
                  FROM teller.transaction tt
             LEFT JOIN teller.transaction_email_match tem
                    ON tem.transaction_id = tt.transaction_id
                   AND tem.active = TRUE
             LEFT JOIN latest_runs lr
                    ON lr.transaction_id = tt.transaction_id
                 WHERE (
                       tt.date >= CURRENT_DATE - (:lookback_days * INTERVAL '1 day')
                    OR lr.transaction_id IS NULL
                 )
                   AND (
                       tem.match_id IS NULL
                       OR tem.state::text = 'ai_candidate_uncertain'
                       OR (tem.state::text = 'ai_no_match_found' AND tem.selected_by::text = 'ai')
                   )
                 ORDER BY COALESCE(lr.completed_at, lr.created_at, to_timestamp(0)) ASC,
                          tt.date DESC,
                          tt.transaction_id ASC
                 LIMIT :limit
                """
            ),
            {"lookback_days": lookback_days, "limit": limit},
        ).mappings().all()
        return [str(row["transaction_id"]) for row in rows]

    #R015: Read the most recent match_run for a transaction plus the stored candidate payload that run scored.
    #R015: Used by MatchService to decide whether the AI call is necessary on this iteration; if the
    #R015: previous run was a real evaluation under the same model+prompt with the same rank-relevant
    #R015: candidate payload as the current search returns, calling Claude again would be a guaranteed no-op.
    def read_last_run_summary(self, session, transaction_id: str) -> dict | None:
        run_row = session.execute(
            text(
                """
                SELECT match_run_id, status::text AS status, model_name, prompt_version
                  FROM teller.transaction_email_match_run
                 WHERE transaction_id = :transaction_id
                 ORDER BY match_run_id DESC
                 LIMIT 1
                """
            ),
            {"transaction_id": transaction_id},
        ).mappings().fetchone()
        if run_row is None:
            return None
        candidate_rows = session.execute(
            text(
                """
                SELECT email_message_id,
                       email_received_at,
                       score,
                       reason_json,
                       cached_subject,
                       cached_sender,
                       cached_snippet,
                       is_unmatched_email_priority
                  FROM teller.transaction_email_candidate
                 WHERE match_run_id = :match_run_id
                """
            ),
            {"match_run_id": run_row["match_run_id"]},
        ).mappings().all()
        return {
            "match_run_id": int(run_row["match_run_id"]),
            "status": str(run_row["status"]),
            "model_name": str(run_row["model_name"]),
            "prompt_version": str(run_row["prompt_version"]),
            "candidate_cache_rows": [
                {
                    "email_message_id": str(row["email_message_id"]),
                    "email_received_at": (
                        row["email_received_at"].isoformat()
                        if row.get("email_received_at") is not None
                        else ""
                    ),
                    "score": float(row["score"]) if row.get("score") is not None else 0.0,
                    "reason_json": row.get("reason_json") or {},
                    "cached_subject": str(row.get("cached_subject") or ""),
                    "cached_sender": str(row.get("cached_sender") or ""),
                    "cached_snippet": str(row.get("cached_snippet") or ""),
                    "is_unmatched_email_priority": bool(row.get("is_unmatched_email_priority")),
                }
                for row in candidate_rows
            ],
        }

    #R015: Read the active match row so service callers can echo the cached AI decision back to clients
    #R015: when they short-circuit on a cache hit (no new AI evaluation was performed this iteration).
    def read_active_match_summary(self, session, transaction_id: str) -> dict | None:
        row = session.execute(
            text(
                """
                SELECT match_id, email_message_id, state::text AS state,
                       ai_confidence, selected_by::text AS selected_by
                  FROM teller.transaction_email_match
                 WHERE transaction_id = :transaction_id
                   AND active = TRUE
                 LIMIT 1
                """
            ),
            {"transaction_id": transaction_id},
        ).mappings().fetchone()
        if row is None:
            return None
        confidence = row.get("ai_confidence")
        return {
            "match_id": int(row["match_id"]),
            "email_message_id": row.get("email_message_id"),
            "state": str(row["state"]),
            "selected_by": str(row["selected_by"]),
            "ai_confidence": float(confidence) if confidence is not None else None,
        }

    def list_active_email_ids_for_other_transactions(self, session, transaction_id: str) -> set[str]:
        rows = session.execute(
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
        return {str(row["email_message_id"]) for row in rows}

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
