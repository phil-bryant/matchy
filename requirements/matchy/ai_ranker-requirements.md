# Matchy AI Ranker Requirements

## Scope

Applies to `matchy/ai_ranker.py`.

R440  Statement: Initialize and select AI backends in deterministic priority order.
Design: `AiRanker` builds Anthropic/OpenAI clients only when keys and SDKs are available, then `select` chooses no-candidate handling, Anthropic, OpenAI, or deterministic fallback in that order.
Tests:
- R440-T01: Construct `AiRanker` without AI keys and verify deterministic selection path is chosen from `select`.
- R440-T02: Call `select` with an empty candidate list and verify it returns the explicit no-candidates response.

R445  Statement: Report the planned model name before evaluation so cache checks can compare model identity.
Design: `planned_model_name` returns Anthropic model when Anthropic client exists, OpenAI model when only OpenAI exists, and `deterministic` when neither client is configured.
Tests:
- R445-T01: Toggle available clients and verify `planned_model_name` returns Anthropic, OpenAI, or deterministic as appropriate.

R450  Statement: Provide deterministic top-candidate fallback when no AI backend is available.
Design: `_select_deterministic` selects top scored candidates meeting threshold, preserves confidence/uncertain outputs, and emits deterministic rationale/backend metadata.
Tests:
- R450-T01: Verify deterministic fallback returns scored candidate ids and deterministic rationale.

R455  Statement: Build prompt payloads that expose bounded candidate evidence for AI disambiguation.
Design: `_build_prompt_payload` emits top candidate rows including normalized `body_excerpt` and explicit output schema/rules so model output is constrained and comparable.
Tests:
- R455-T01: Build prompt payload and verify each candidate row includes wrapped `body_excerpt` and expected schema keys.

R460  Statement: Normalize raw email body text into compact plain-text excerpts for prompts.
Design: `_extract_body_excerpt` strips script/style blocks and tags, collapses whitespace, and truncates to configured caps; missing body text yields empty string.
Tests:
- R460-T01: Verify HTML-rich body text is normalized and truncated to `_BODY_TEXT_PROMPT_MAX`.

R465  Statement: Delimit body excerpts as untrusted content and redact embedded delimiter tokens.
Design: `_delimit_untrusted_body_excerpt` replaces embedded delimiter tokens with redacted sentinels and wraps the final excerpt between canonical begin/end markers.
Tests:
- R465-T01: Verify embedded delimiter tokens are redacted while outer canonical delimiters remain intact.

R470  Statement: Retry Anthropic failures with bounded backoff and prompt shrinking.
Design: `_select_with_anthropic` retries up to three attempts with smaller body excerpt caps for rate-limit/context errors and honors `Retry-After` when provided by `_retry_after_seconds`.
Tests:
- R470-T01: Stub Anthropic to raise a rate limit once and verify retry succeeds on the next shrunken attempt.

R475  Statement: Parse OpenAI/Anthropic text payloads defensively into safe `AiSelection` objects.
Design: `_select_with_openai` delegates to `_parse_ai_payload`; parser strips markdown fences, extracts balanced JSON from prose, clamps confidence to `[0,1]`, and falls back safely on malformed payloads.
Tests:
- R475-T01: Parse malformed JSON and verify safe defaults.
- R475-T02: Parse fenced JSON payload and verify structured values are retained.
- R475-T03: Parse prose-padded JSON and verify balanced object extraction succeeds.

## Changelog

- 2026-05-18: Added AI ranker requirements and numbered test traceability.
- 2026-05-19: Added R010 body-excerpt extraction so the AI prompt sees email content (not just bodyPreview) to disambiguate same-day same-merchant candidates.
- 2026-05-19: Added R015 fence-tolerant + object-extraction JSON parsing so Claude responses wrapped in ```` ``` ```` fences (the observed default behavior) are no longer silently dropped.
- 2026-05-19: Added R020 retry-with-shrink so Anthropic 429s during a matchy batch no longer abort the batch and instead shrink the prompt for that transaction before re-trying.
- 2026-06-04: Added R030 untrusted-body delimiter handling so prompt payloads isolate email-body content and redact embedded delimiter tokens.
- 2026-06-06: Rebased AI ranker traceability onto shard-1 ID band R440-R475 with anchored tests.
