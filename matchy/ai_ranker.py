from __future__ import annotations

import json

from .models import AiSelection, RankedCandidate, TransactionInput
from .settings import Settings


PROMPT_VERSION = "v1"

_OUTPUT_JSON_NOTE = (
    "Return ONLY a JSON object with keys selected_message_ids (list of strings),"
    " confidence (number 0..1), uncertain (boolean), rationale (string). No prose."
)


class AiRanker:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._anthropic_client = self._build_anthropic_client(settings)
        self._openai_client = None
        if self._anthropic_client is None:
            self._openai_client = self._build_openai_client(settings)

    def _build_anthropic_client(self, settings: Settings):
        client = None
        if settings.anthropic_api_key:
            try:
                from anthropic import Anthropic
                client = Anthropic(api_key=settings.anthropic_api_key)
            except ImportError:
                client = None
        return client

    def _build_openai_client(self, settings: Settings):
        client = None
        if settings.openai_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.openai_api_key)
            except ImportError:
                client = None
        return client

    def select(self, transaction: TransactionInput, ranked_candidates: list[RankedCandidate]) -> AiSelection:
        selection: AiSelection
        if not ranked_candidates:
            selection = AiSelection(selected_message_ids=[], confidence=0.0, uncertain=True, rationale="No candidates found.")
        elif self._anthropic_client is not None:
            selection = self._select_with_anthropic(transaction, ranked_candidates)
        elif self._openai_client is not None:
            selection = self._select_with_openai(transaction, ranked_candidates)
        else:
            selection = self._select_deterministic(ranked_candidates)
        return selection

    #R001: Fallback to deterministic top-candidate selection when no AI client is available.
    def _select_deterministic(self, ranked_candidates: list[RankedCandidate]) -> AiSelection:
        top = ranked_candidates[:2]
        return AiSelection(
            selected_message_ids=[row.candidate.message_id for row in top if row.score >= 0.60],
            confidence=top[0].score if top else 0.0,
            uncertain=(top[0].score < 0.9) if top else True,
            rationale="No AI key available via 1psa or env; used deterministic fallback.",
        )

    def _build_prompt_payload(self, transaction: TransactionInput, ranked_candidates: list[RankedCandidate]) -> dict:
        candidate_rows = []
        for ranked in ranked_candidates[:10]:
            candidate_rows.append({
                "message_id": ranked.candidate.message_id,
                "subject": ranked.candidate.subject,
                "preview": ranked.candidate.preview[:300],
                "received_at": ranked.candidate.received_at.isoformat(),
                "deterministic_score": ranked.score,
                "reasons": ranked.reasons,
            })
        payload = {
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
        return payload

    def _select_with_anthropic(self, transaction: TransactionInput, ranked_candidates: list[RankedCandidate]) -> AiSelection:
        prompt = self._build_prompt_payload(transaction, ranked_candidates)
        user_text = f"{_OUTPUT_JSON_NOTE}\n\n{json.dumps(prompt)}"
        message = self._anthropic_client.messages.create(
            model=self._settings.anthropic_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": user_text}],
        )
        text_payload = ""
        for block in message.content:
            if getattr(block, "type", "") == "text":
                text_payload += block.text
        return self._parse_ai_payload(text_payload.strip() or "{}", "anthropic")

    def _select_with_openai(self, transaction: TransactionInput, ranked_candidates: list[RankedCandidate]) -> AiSelection:
        prompt = self._build_prompt_payload(transaction, ranked_candidates)
        response = self._openai_client.responses.create(
            model=self._settings.openai_model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": json.dumps(prompt)}]}],
        )
        text_payload = response.output_text.strip() or "{}"
        return self._parse_ai_payload(text_payload, "openai")

    #R005: Parse AI JSON defensively and return safe defaults when payloads are malformed or incomplete.
    def _parse_ai_payload(self, text_payload: str, backend: str) -> AiSelection:
        parsed: dict = {}
        try:
            parsed = json.loads(text_payload)
        except json.JSONDecodeError:
            parsed = {}
        return AiSelection(
            selected_message_ids=[str(item) for item in parsed.get("selected_message_ids", [])],
            confidence=float(parsed.get("confidence", 0.0)),
            uncertain=bool(parsed.get("uncertain", True)),
            rationale=str(parsed.get("rationale", f"No rationale provided by {backend}.")),
        )
