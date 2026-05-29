from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .models import AiSelection, RankedCandidate, TransactionInput
from .settings import Settings


class MatchRepository:
    #R001: Refuse repository initialization when Teller DB credentials are unavailable.
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

    #R005: Commit successful unit-of-work sessions and rollback on failures.
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

    #R015: Read the most recent match_run for a transaction plus the candidate id set that run scored.
    #R015: Used by MatchService to decide whether the AI call is necessary on this iteration; if the
    #R015: previous run was a real evaluation under the same model+prompt with the same candidate id
    #R015: set as the current search returns, calling Claude again would be a guaranteed no-op.
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
                SELECT email_message_id
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
            "candidate_message_ids": [str(row["email_message_id"]) for row in candidate_rows],
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

    #R030: Persist subject/sender/preview into cached_* columns at candidate-insert time so
    #R030: downstream UIs (Teller's Match & Classify candidates pane) can render without paying
    #R030: another per-message Mailcart round-trip per row. Matchy already pulls this metadata
    #R030: from Mailcart (search response + body enrichment) so persisting it is free at this point.
    def insert_candidates(self, session, match_run_id: int, transaction_id: str, candidates: list[RankedCandidate], ai_selected_ids: set[str]) -> None:
        for ranked in candidates:
            preview = ranked.candidate.preview or ranked.candidate.body_text[:240] if ranked.candidate.body_text else ranked.candidate.preview
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
                        is_selected_by_ai,
                        cached_subject,
                        cached_sender,
                        cached_snippet,
                        cached_fetched_at
                    ) VALUES (
                        :match_run_id,
                        :transaction_id,
                        :email_message_id,
                        :email_received_at,
                        :score,
                        CAST(:reason_json AS jsonb),
                        :is_unmatched_email_priority,
                        :is_selected_by_ai,
                        :cached_subject,
                        :cached_sender,
                        :cached_snippet,
                        CASE WHEN :cached_subject IS NULL AND :cached_sender IS NULL AND :cached_snippet IS NULL
                             THEN NULL ELSE CURRENT_TIMESTAMP END
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
                    "cached_subject": (ranked.candidate.subject or None),
                    "cached_sender": (ranked.candidate.sender or None),
                    "cached_snippet": (preview or None),
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
        conflict_detected = False
        session.execute(
            text(
                """
                UPDATE teller.transaction_email_match
                   SET active = FALSE,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE transaction_id = :transaction_id
                   AND active = TRUE
                """
            ),
            {"transaction_id": transaction_id},
        )

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
                conflict_detected = True
                continue
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

        if conflict_detected and not selected:
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
                        'ai_candidate_uncertain',
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
                        {
                            "rationale": ai_selection.rationale,
                            "run_id": run_id,
                            "reason": "selected_email_already_has_active_match",
                        }
                    ),
                    "selected_at": now,
                },
            )
            state = "ai_candidate_uncertain"

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
