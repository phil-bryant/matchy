from __future__ import annotations

import hashlib
import json
import logging

from .ai_ranker import PROMPT_VERSION
from .models import EmailCandidate

LOGGER = logging.getLogger(__name__)

#R020: Statuses that represent a completed AI evaluation; only these are cache-eligible. `failed`
#R020: runs are NOT in this set so transient errors (Mailcart down, Anthropic 404, etc.) self-heal
#R020: on the next loop instead of being permanently cached as no-ops.
_CACHE_HIT_STATUSES = frozenset({"succeeded", "needs_review", "no_candidates"})


class CachingMixin:
    def _ranked_candidate_cache_rows(self, ranked_candidates) -> list[dict]:
        rows: list[dict] = []
        for ranked in ranked_candidates:
            candidate = ranked.candidate
            reasons = ranked.reasons or {}
            preview = candidate.preview or (candidate.body_text[:240] if candidate.body_text else candidate.preview)
            rows.append(
                {
                    "email_message_id": str(candidate.message_id),
                    "email_received_at": candidate.received_at.isoformat() if candidate.received_at is not None else "",
                    "score": float(ranked.score),
                    "reason_json": reasons,
                    "cached_subject": str(candidate.subject or ""),
                    "cached_sender": str(candidate.sender or ""),
                    "cached_snippet": str(preview or ""),
                    "is_unmatched_email_priority": bool(reasons.get("unmatched_email_priority", False)),
                }
            )
        return rows

    #R020: Decide whether the previous AI verdict still applies. Returns a cached response dict (the
    #R020: same shape as a fresh evaluation, with `skipped=True`) when all of these hold:
    #R020:   - a prior run exists,
    #R020:   - its status was a real completed evaluation (`_CACHE_HIT_STATUSES`),
    #R020:   - its model_name matches what the current ranker would use,
    #R020:   - its prompt_version matches the current `PROMPT_VERSION`, and
    #R020:   - its ranked candidate payload hash is byte-identical to the current pre-AI ranking.
    #R020: Returns None to indicate the caller should fall through to the full AI pipeline.
    #R020: force_rematch bypasses the prompt_version (v2/v3) cache so new prompts take effect immediately.
    def _maybe_cached_response(
        self,
        session,
        transaction_id: str,
        candidates: list[EmailCandidate],
        planned_model: str,
        current_hash: str,
        current_message_id_hash: str = "",
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
        cached_rows = last_summary.get("candidate_cache_rows")
        if cached_rows is None:
            cached_hash = self._candidate_message_id_hash(last_summary.get("candidate_message_ids", []))
            if cached_hash != current_message_id_hash:
                return None
        else:
            cached_hash = self._candidate_set_hash(cached_rows)
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
            "skip_reason": "candidate_signature_unchanged_for_model_and_prompt",
            "state": active.get("state") if active else None,
        }

    #R020: Deterministic, order-independent fingerprint of rank/scoring-relevant candidate payload.
    @staticmethod
    def _candidate_set_hash(candidate_cache_rows: list[dict]) -> str:
        digest = hashlib.sha256()
        normalized_rows = []
        for row in candidate_cache_rows:
            normalized_rows.append(
                {
                    "email_message_id": str(row.get("email_message_id") or ""),
                    "email_received_at": str(row.get("email_received_at") or ""),
                    "score": f"{float(row.get('score') or 0.0):0.8f}",
                    "reason_json": row.get("reason_json") or {},
                    "cached_subject": str(row.get("cached_subject") or ""),
                    "cached_sender": str(row.get("cached_sender") or ""),
                    "cached_snippet": str(row.get("cached_snippet") or ""),
                    "is_unmatched_email_priority": bool(row.get("is_unmatched_email_priority")),
                }
            )
        normalized_rows = sorted(
            normalized_rows,
            key=lambda row: (row["email_message_id"], row["email_received_at"], row["cached_snippet"]),
        )
        for row in normalized_rows:
            digest.update(json.dumps(row, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()

    @staticmethod
    def _candidate_message_id_hash(message_ids: list[str]) -> str:
        digest = hashlib.sha256()
        for message_id in sorted(str(item) for item in message_ids):
            digest.update(message_id.encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()
