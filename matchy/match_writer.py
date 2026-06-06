from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from .models import AiSelection, RankedCandidate


class MatchWriterMixin:
    #R680: Persist subject/sender/preview into cached_* columns at candidate-insert time so
    #R680: downstream UIs can render candidate rows without extra Mailcart fetches.
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

    #R685: Detect whether a candidate email already has an active match row.
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

    #R690: Persist AI selection outcomes into transaction_email_match rows and run status updates.
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
        candidate_message_ids = {ranked.candidate.message_id for ranked in ranked_candidates}
        selected_ids = set(ai_selection.selected_message_ids) & candidate_message_ids
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

    #R695: Deactivate all active match rows for a transaction before replacing or confirming matches.
    def deactivate_active_match(self, session, transaction_id: str) -> None:
        session.execute(
            text(
                """
                UPDATE teller.transaction_email_match
                   SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                 WHERE transaction_id = :transaction_id AND active = TRUE
                """
            ),
            {"transaction_id": transaction_id},
        )

    #R700: Insert and return a human-confirmed match row with optional note metadata.
    def insert_human_confirmed_match(self, session, transaction_id: str, email_message_id: str, note: str | None) -> int:
        now = datetime.now(tz=timezone.utc)
        explanation = {"note": note} if note else {}
        return int(
            session.execute(
                text(
                    """
                    INSERT INTO teller.transaction_email_match (
                        transaction_id, email_message_id, state, selected_by, selected_at, active, explanation_json
                    ) VALUES (
                        :transaction_id, :email_message_id, 'human_confirmed_ai_match', 'human', :selected_at, TRUE, CAST(:explanation AS jsonb)
                    )
                    RETURNING match_id
                    """
                ),
                {
                    "transaction_id": transaction_id,
                    "email_message_id": email_message_id,
                    "selected_at": now,
                    "explanation": __import__("json").dumps(explanation),
                },
            ).scalar_one()
        )
