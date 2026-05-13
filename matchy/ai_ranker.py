from __future__ import annotations

import json

from openai import OpenAI

from .models import AiSelection, RankedCandidate, TransactionInput
from .settings import Settings


PROMPT_VERSION = "v1"


class AiRanker:
    def __init__(self, settings: Settings):
        self._model = settings.openai_model
        self._client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def select(self, transaction: TransactionInput, ranked_candidates: list[RankedCandidate]) -> AiSelection:
        if not ranked_candidates:
            return AiSelection(selected_message_ids=[], confidence=0.0, uncertain=True, rationale="No candidates found.")
        if self._client is None:
            top = ranked_candidates[:2]
            return AiSelection(
                selected_message_ids=[row.candidate.message_id for row in top if row.score >= 0.60],
                confidence=top[0].score if top else 0.0,
                uncertain=(top[0].score < 0.9),
                rationale="OpenAI key unavailable; used deterministic fallback.",
            )

        candidate_rows = []
        for ranked in ranked_candidates[:10]:
            candidate_rows.append(
                {
                    "message_id": ranked.candidate.message_id,
                    "subject": ranked.candidate.subject,
                    "preview": ranked.candidate.preview[:300],
                    "received_at": ranked.candidate.received_at.isoformat(),
                    "deterministic_score": ranked.score,
                    "reasons": ranked.reasons,
                }
            )
        prompt = {
            "task": "Select email ids that belong to one transaction. 1 transaction may map to multiple emails.",
            "rules": [
                "Do not choose speculative candidates with weak evidence.",
                "Prefer candidates near transaction date, but delayed receipts are possible.",
                "Return JSON only.",
            ],
            "transaction": {
                "transaction_id": transaction.transaction_id,
                "amount": str(transaction.amount),
                "date": transaction.date.isoformat(),
                "description": transaction.description,
                "counterparty_name": transaction.counterparty_name,
            },
            "candidates": candidate_rows,
            "output_schema": {
                "selected_message_ids": ["string"],
                "confidence": "float 0..1",
                "uncertain": "boolean",
                "rationale": "string",
            },
        }
        response = self._client.responses.create(
            model=self._model,
            input=[
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(prompt)}],
                }
            ],
        )
        text_payload = response.output_text.strip() or "{}"
        try:
            parsed = json.loads(text_payload)
        except json.JSONDecodeError:
            parsed = {}
        return AiSelection(
            selected_message_ids=[str(item) for item in parsed.get("selected_message_ids", [])],
            confidence=float(parsed.get("confidence", 0.0)),
            uncertain=bool(parsed.get("uncertain", True)),
            rationale=str(parsed.get("rationale", "No rationale provided.")),
        )
