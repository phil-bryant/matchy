from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import date, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from teller.teller_db import get_engine
from teller.teller_db_profile import reset_profile_cache

from .db_target import as_datetime, is_sqlite, sql_for_target
from .match_writer import MatchWriterMixin
from .models import TransactionInput
from .settings import Settings


#R035: Resolve owned-schema table references for the active backend target.
def _sql(sql_text: str):
    return text(sql_for_target(sql_text))


class MatchRepository(MatchWriterMixin):
    #R001: Bind the repository to the profile-driven teller DB engine so matchy
    #R001: switches between PostgreSQL and SQLite/SQLCipher like teller does.
    def __init__(self, settings: Settings):
        self._write_enabled = bool(getattr(settings, "write_enabled", True))
        #R001: Matchy writes to the matchy.* schema as the profile's base user;
        #R001: teller's default `SET ROLE` runtime role (teller_write) only holds
        #R001: teller-schema privileges. Default the role override off while
        #R001: keeping TELLER_DB_ROLE honored when explicitly set. The profile
        #R001: cache key cannot distinguish unset from empty env, so reset it
        #R001: when installing the default.
        if "TELLER_DB_ROLE" not in os.environ:
            os.environ["TELLER_DB_ROLE"] = ""
            reset_profile_cache()
        self._engine = get_engine()
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

    #R720: Load a single transaction row (with optional counterparty) and normalize it into TransactionInput with UTC timestamp.
    def load_transaction(self, session, transaction_id: str) -> TransactionInput | None:
        row = session.execute(
            _sql(
                """
                SELECT tt.transaction_id,
                       tt.account_id,
                       tt.amount,
                       tt.date AS date_value,
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
        #R720: SQLite stores money as integer cents; PostgreSQL stores numeric dollars.
        amount = Decimal(row["amount"])
        if is_sqlite():
            amount = amount / Decimal(100)
        date_ts = as_datetime(row["date_value"])
        if date_ts is None:
            return None
        return TransactionInput(
            transaction_id=row["transaction_id"],
            account_id=row["account_id"],
            amount=amount,
            date=date_ts.replace(tzinfo=timezone.utc),
            description=row["description"],
            counterparty_name=row["counterparty_name"] or "",
        )

    #R721: Create a new match run row initialized to needs_review and return its generated match_run_id.
    def create_run(self, session, transaction_id: str, trigger_source: str, model_name: str, prompt_version: str) -> int:
        params = {
            "transaction_id": transaction_id,
            "trigger_source": trigger_source,
            "model_name": model_name,
            "prompt_version": prompt_version,
        }
        insert_sql = """
            INSERT INTO matchy.transaction_email_match_run (
                transaction_id, trigger_source, model_name, prompt_version, status
            ) VALUES (
                :transaction_id, :trigger_source, :model_name, :prompt_version, 'needs_review'
            )
        """
        if is_sqlite():
            #R721: pysqlcipher3 cannot surface INSERT..RETURNING rows; use last_insert_rowid().
            session.execute(_sql(insert_sql), params)
            return int(session.execute(text("SELECT last_insert_rowid()")).scalar_one())
        return int(
            session.execute(
                _sql(insert_sql + " RETURNING match_run_id"),
                params,
            ).scalar_one()
        )

    #R722: Update an existing match run's recorded model name without mutating other run columns.
    def update_run_model_name(self, session, run_id: int, model_name: str) -> None:
        session.execute(
            _sql(
                """
                UPDATE matchy.transaction_email_match_run
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
        #R010: Window-function ranking and bound cutoff/epoch values keep this
        #R010: query portable across PostgreSQL and SQLite.
        cutoff_date = (date.today() - timedelta(days=lookback_days)).isoformat()
        rows = session.execute(
            _sql(
                """
                WITH latest_runs AS (
                    SELECT transaction_id, created_at, completed_at
                      FROM (
                        SELECT temr.transaction_id,
                               temr.created_at,
                               temr.completed_at,
                               ROW_NUMBER() OVER (
                                   PARTITION BY temr.transaction_id
                                   ORDER BY temr.match_run_id DESC
                               ) AS rn
                          FROM matchy.transaction_email_match_run temr
                      ) ranked
                     WHERE ranked.rn = 1
                )
                SELECT tt.transaction_id
                  FROM teller.transaction tt
             LEFT JOIN matchy.transaction_email_match tem
                    ON tem.transaction_id = tt.transaction_id
                   AND tem.active = TRUE
             LEFT JOIN latest_runs lr
                    ON lr.transaction_id = tt.transaction_id
                 WHERE (
                       tt.date >= :cutoff_date
                    OR lr.transaction_id IS NULL
                 )
                   AND (
                       tem.match_id IS NULL
                       OR CAST(tem.state AS TEXT) = 'ai_candidate_uncertain'
                       OR (CAST(tem.state AS TEXT) = 'ai_no_match_found' AND CAST(tem.selected_by AS TEXT) = 'ai')
                   )
                 ORDER BY COALESCE(lr.completed_at, lr.created_at, :epoch) ASC,
                          tt.date DESC,
                          tt.transaction_id ASC
                 LIMIT :limit
                """
            ),
            {"cutoff_date": cutoff_date, "epoch": "1970-01-01 00:00:00", "limit": limit},
        ).mappings().all()
        return [str(row["transaction_id"]) for row in rows]

    #R015: Read the most recent match_run for a transaction plus the stored candidate payload that run scored.
    #R015: Used by MatchService to decide whether the AI call is necessary on this iteration; if the
    #R015: previous run was a real evaluation under the same model+prompt with the same rank-relevant
    #R015: candidate payload as the current search returns, calling Claude again would be a guaranteed no-op.
    def read_last_run_summary(self, session, transaction_id: str) -> dict | None:
        run_row = session.execute(
            _sql(
                """
                SELECT match_run_id, CAST(status AS TEXT) AS status, model_name, prompt_version
                  FROM matchy.transaction_email_match_run
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
            _sql(
                """
                SELECT email_message_id,
                       email_received_at,
                       score,
                       reason_json,
                       cached_subject,
                       cached_sender,
                       cached_snippet,
                       is_unmatched_email_priority
                  FROM matchy.transaction_email_candidate
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
                        received.isoformat()
                        if (received := as_datetime(row.get("email_received_at"))) is not None
                        else ""
                    ),
                    "score": float(row["score"]) if row.get("score") is not None else 0.0,
                    "reason_json": _parsed_reason_json(row.get("reason_json")),
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
            _sql(
                """
                SELECT match_id, email_message_id, CAST(state AS TEXT) AS state,
                       ai_confidence, CAST(selected_by AS TEXT) AS selected_by
                  FROM matchy.transaction_email_match
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

    #R723: List active email_message_ids already attached to other transactions to prevent duplicate active matches.
    def list_active_email_ids_for_other_transactions(self, session, transaction_id: str) -> set[str]:
        rows = session.execute(
            _sql(
                """
                SELECT email_message_id
                  FROM matchy.transaction_email_match
                 WHERE active = TRUE
                   AND email_message_id IS NOT NULL
                   AND transaction_id <> :transaction_id
                """
            ),
            {"transaction_id": transaction_id},
        ).mappings().all()
        return {str(row["email_message_id"]) for row in rows}

    #R724: Mark a match run complete with status/error metadata while stamping completed_at.
    def _update_run_status(self, session, run_id: int, status: str, error_text: str | None = None) -> None:
        session.execute(
            _sql(
                """
                UPDATE matchy.transaction_email_match_run
                   SET status = :status,
                       completed_at = CURRENT_TIMESTAMP,
                       error_text = :error_text
                 WHERE match_run_id = :match_run_id
                """
            ),
            {"status": status, "error_text": error_text, "match_run_id": run_id},
        )

    #R725: Mark a match run as failed by delegating to the shared run-status update helper.
    def mark_run_failed(self, session, run_id: int, error_text: str) -> None:
        self._update_run_status(session, run_id, "failed", error_text=error_text)


#R015: JSON candidate metadata arrives parsed (jsonb) on PostgreSQL and as text on SQLite.
def _parsed_reason_json(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
