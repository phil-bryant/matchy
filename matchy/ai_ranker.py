from __future__ import annotations

import json

from .models import AiSelection, RankedCandidate, TransactionInput
from .settings import Settings


PROMPT_VERSION = "v3"

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
            selection = AiSelection(
                selected_message_ids=[],
                confidence=0.0,
                uncertain=True,
                rationale="No candidates found.",
                backend="none",
                model_name="none:no_candidates",
            )
        elif self._anthropic_client is not None:
            selection = self._select_with_anthropic(transaction, ranked_candidates)
        elif self._openai_client is not None:
            selection = self._select_with_openai(transaction, ranked_candidates)
        else:
            selection = self._select_deterministic(ranked_candidates)
        return selection

    def planned_model_name(self) -> str:
        model_name = "deterministic"
        if self._anthropic_client is not None:
            model_name = self._settings.anthropic_model
        if self._anthropic_client is None and self._openai_client is not None:
            model_name = self._settings.openai_model
        return model_name

    #R001: Fallback to deterministic top-candidate selection when no AI client is available.
    def _select_deterministic(self, ranked_candidates: list[RankedCandidate]) -> AiSelection:
        top = ranked_candidates[:2]
        return AiSelection(
            selected_message_ids=[row.candidate.message_id for row in top if row.score >= 0.60],
            confidence=top[0].score if top else 0.0,
            uncertain=(top[0].score < 0.9) if top else True,
            rationale="No AI key available via 1psa or env; used deterministic fallback.",
            backend="deterministic",
            model_name="deterministic",
        )

    #R010: Include a truncated body excerpt in the AI prompt so the model can disambiguate same-day
    #R010: same-merchant emails by their actual content (e.g., the fare amount embedded in HTML body,
    #R010: which is not visible in Graph's bodyPreview). Body text is bounded per candidate to keep the
    #R010: total prompt manageable across the top-10 ranked candidates.
    _BODY_TEXT_PROMPT_MAX = 2000

    def _build_prompt_payload(
        self,
        transaction: TransactionInput,
        ranked_candidates: list[RankedCandidate],
        body_excerpt_cap: int | None = None,
    ) -> dict:
        candidate_rows = []
        effective_cap = body_excerpt_cap if body_excerpt_cap is not None else self._BODY_TEXT_PROMPT_MAX
        for ranked in ranked_candidates[:10]:
            body_excerpt = self._extract_body_excerpt(ranked.candidate.body_text, max_chars=effective_cap)
            candidate_rows.append({
                "message_id": ranked.candidate.message_id,
                "subject": ranked.candidate.subject,
                "preview": ranked.candidate.preview[:300],
                "body_excerpt": body_excerpt,
                "received_at": ranked.candidate.received_at.isoformat(),
                "deterministic_score": ranked.score,
                "reasons": ranked.reasons,
            })
        payload = {
            "task": "Select email ids that belong to one transaction. 1 transaction may map to multiple emails.",
            "rules": [
                "Do not choose speculative candidates with weak evidence.",
                "Prefer candidates near transaction date, but delayed receipts are possible.",
                "Use body_excerpt to verify amounts and disambiguate same-day same-merchant emails.",
                "If none of the candidate emails contain a clear receipt, invoice, order confirmation, payment acknowledgment, or other transaction-related document whose merchant, amount, or date are plausibly related to the input transaction, assign ai_confidence ≤ 0.30 and strongly prefer returning no selected_message_ids (ai_no_match_found) over selecting a low-quality match. Do not inflate confidence merely because one candidate is the \"least bad\" option among irrelevant emails. When in doubt, be conservative.",
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

    #R010: Reduce body text to a compact, mostly-text excerpt. Strips obvious HTML markup so the AI
    #R010: model receives readable content rather than CSS/img tags, then truncates to the configured
    #R010: per-candidate cap (or an override when the AI ranker is shrinking the prompt on a rate-limit
    #R010: retry). Falls back to the empty string when body_text is missing.
    def _extract_body_excerpt(self, body_text: str, max_chars: int | None = None) -> str:
        if not body_text:
            return ""
        import re as _re
        without_scripts = _re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body_text)
        without_tags = _re.sub(r"(?s)<[^>]+>", " ", without_scripts)
        collapsed = _re.sub(r"\s+", " ", without_tags).strip()
        limit = max_chars if max_chars is not None else self._BODY_TEXT_PROMPT_MAX
        return collapsed[: max(0, int(limit))]

    #R020: Anthropic enforces an input-tokens-per-minute organization rate limit. When the prompt
    #R020: exceeds that limit we either need to back off (retry-after the Retry-After header) or
    #R020: shrink the prompt for that retry. We retry up to three times with progressively shorter
    #R020: body excerpts (full → 1000 → 500 chars) so a single noisy transaction does not abort the
    #R020: driver's batch loop and so the next loop sees fewer pending rows on the next minute.
    def _select_with_anthropic(self, transaction: TransactionInput, ranked_candidates: list[RankedCandidate]) -> AiSelection:
        import time
        from anthropic import APIStatusError, RateLimitError

        body_caps = [None, 1000, 500]
        for attempt, cap in enumerate(body_caps):
            prompt = self._build_prompt_payload(transaction, ranked_candidates, body_excerpt_cap=cap)
            user_text = f"{_OUTPUT_JSON_NOTE}\n\n{json.dumps(prompt)}"
            try:
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
            except RateLimitError as exc:
                if attempt == len(body_caps) - 1:
                    raise
                retry_after = self._retry_after_seconds(exc) or (2 ** attempt) * 5
                time.sleep(min(retry_after, 60))
                continue
            except APIStatusError as exc:
                # Some upstream 400s also report "too long" — treat as retry-with-shrink.
                detail = str(getattr(exc, "message", "") or exc).lower()
                if "too long" in detail or "max_tokens" in detail or "context" in detail:
                    if attempt < len(body_caps) - 1:
                        continue
                raise

    @staticmethod
    def _retry_after_seconds(exc) -> float | None:
        response = getattr(exc, "response", None)
        if response is None:
            return None
        headers = getattr(response, "headers", {}) or {}
        for key in ("retry-after", "Retry-After"):
            value = headers.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    def _select_with_openai(self, transaction: TransactionInput, ranked_candidates: list[RankedCandidate]) -> AiSelection:
        prompt = self._build_prompt_payload(transaction, ranked_candidates)
        response = self._openai_client.responses.create(
            model=self._settings.openai_model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": json.dumps(prompt)}]}],
        )
        text_payload = response.output_text.strip() or "{}"
        return self._parse_ai_payload(text_payload, "openai")

    #R005: Parse AI JSON defensively and return safe defaults when payloads are malformed or incomplete.
    #R015: Tolerate models (e.g., Claude) that wrap JSON in ``` markdown fences or pad it with prose
    #R015: even when the prompt says "JSON only" — strip a single leading/trailing fence block, then
    #R015: fall back to extracting the first balanced {...} object before declaring the payload bad.
    def _parse_ai_payload(self, text_payload: str, backend: str) -> AiSelection:
        parsed: dict = {}
        candidate = self._strip_markdown_fences(text_payload)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            extracted = self._extract_first_json_object(candidate)
            if extracted is not None:
                try:
                    parsed = json.loads(extracted)
                except json.JSONDecodeError:
                    parsed = {}
            else:
                parsed = {}
        return AiSelection(
            selected_message_ids=[str(item) for item in parsed.get("selected_message_ids", [])],
            confidence=float(parsed.get("confidence", 0.0)),
            uncertain=bool(parsed.get("uncertain", True)),
            rationale=str(parsed.get("rationale", f"No rationale provided by {backend}.")),
            backend=backend,
            model_name=self._settings.anthropic_model if backend == "anthropic" else self._settings.openai_model,
        )

    #R015: Strip a single leading/trailing markdown code fence (```json ... ``` or ``` ... ```) so
    #R015: model outputs that wrap JSON in fences (Claude is a frequent offender) still parse.
    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        # Drop the opening fence line (``` or ```json or ```JSON ...)
        first_newline = stripped.find("\n")
        if first_newline == -1:
            return stripped
        stripped = stripped[first_newline + 1 :]
        # Drop trailing closing fence if present
        if stripped.rstrip().endswith("```"):
            closing = stripped.rstrip().rfind("```")
            stripped = stripped[:closing]
        return stripped.strip()

    #R015: Find the first balanced JSON object in `text` so trailing prose or extra prefixes do not
    #R015: defeat parsing. Tracks brace depth and respects string literals + backslash escapes.
    @staticmethod
    def _extract_first_json_object(text: str) -> str | None:
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            character = text[index]
            if in_string:
                if escape:
                    escape = False
                elif character == "\\":
                    escape = True
                elif character == '"':
                    in_string = False
                continue
            if character == '"':
                in_string = True
                continue
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None
