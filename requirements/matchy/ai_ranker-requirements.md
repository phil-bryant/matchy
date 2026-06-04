# Matchy AI Ranker Requirements

## Scope

Applies to `matchy/ai_ranker.py`.

R001  Statement: Provide deterministic fallback selection when no AI client is available.
Design: When Anthropic and OpenAI clients are unavailable, select from the top ranked candidates using score threshold and fallback rationale.
Tests:
- R001-T01: Construct `AiRanker` with no API keys and verify fallback selection is used.

R005  Statement: Parse AI JSON payloads defensively with safe defaults.
Design: Decode model payloads into `AiSelection`, defaulting missing/invalid fields to safe values when parsing fails.
Tests:
- R005-T01: Parse malformed JSON and verify empty selection with zero confidence and uncertainty.

R010  Statement: Include a truncated email body excerpt in the AI prompt payload so the model can disambiguate same-day same-merchant candidates by their actual content.
Design: `_build_prompt_payload` adds a `body_excerpt` field to each candidate row, populated by `_extract_body_excerpt` which strips HTML markup (including `<script>`/`<style>` blocks), collapses whitespace, and truncates to `_BODY_TEXT_PROMPT_MAX` (default 2000) characters. Empty `body_text` produces an empty excerpt without raising.
Tests:
- R010-T01: Provide a candidate whose `body_text` contains HTML markup including the transaction amount and verify the excerpt is markup-free, whitespace-collapsed, and bounded by `_BODY_TEXT_PROMPT_MAX`.
- R010-T02: Provide an empty `body_text` and verify the extractor returns the empty string without error.

R020  Statement: Retry-with-shrink on Anthropic rate-limit and context-length errors.
Design: `_select_with_anthropic` retries up to three times when Anthropic raises `RateLimitError` (HTTP 429) or an `APIStatusError` whose message references "too long"/"max_tokens"/"context". Each retry rebuilds the prompt with a progressively smaller `body_excerpt_cap` (None → 1000 → 500 chars), honoring the upstream `Retry-After` header (capped at 60 s) before retrying. After exhausting the retry budget the final exception propagates so the outer service can record a `failed` run and let the next driver loop try again.
Tests:
- R020-T01: Stub the Anthropic client to raise `RateLimitError` then return a valid payload and verify `_select_with_anthropic` returns the parsed selection after shrinking the body excerpt.

R030  Statement: Delimit body excerpts as untrusted payload to reduce prompt-injection risk from email-body instructions.
Design: `_delimit_untrusted_body_excerpt` wraps every candidate body excerpt between fixed boundary tokens (`[[BEGIN_UNTRUSTED_EMAIL_BODY]]` / `[[END_UNTRUSTED_EMAIL_BODY]]`) and redacts any embedded copies of those boundary tokens from source content before wrapping.
Tests:
- R030-T01: Build a prompt payload from a candidate body containing embedded delimiter tokens and verify boundary tokens are redacted in-content while the wrapped excerpt still uses the canonical outer delimiters.

R015  Statement: Tolerate models that wrap JSON output in markdown fences or pad it with prose.
Design: `_parse_ai_payload` strips a single leading/trailing ```` ``` ```` fence (with or without a `json` language hint) via `_strip_markdown_fences`, then if `json.loads` still fails, attempts to extract the first balanced `{...}` object via `_extract_first_json_object` (which respects string literals and backslash escapes). Only when both attempts fail does the parser fall back to the default empty-selection AiSelection.
Tests:
- R015-T01: Feed `_parse_ai_payload` a Claude-style ```` ```json\n{...}\n``` ```` payload and verify the selected ids, confidence, and rationale come from the inner JSON.
- R015-T02: Feed `_parse_ai_payload` a JSON object surrounded by leading/trailing prose and verify the embedded object is still parsed.

## Changelog

- 2026-05-18: Added AI ranker requirements and numbered test traceability.
- 2026-05-19: Added R010 body-excerpt extraction so the AI prompt sees email content (not just bodyPreview) to disambiguate same-day same-merchant candidates.
- 2026-05-19: Added R015 fence-tolerant + object-extraction JSON parsing so Claude responses wrapped in ```` ``` ```` fences (the observed default behavior) are no longer silently dropped.
- 2026-05-19: Added R020 retry-with-shrink so Anthropic 429s during a matchy batch no longer abort the batch and instead shrink the prompt for that transaction before re-trying.
- 2026-06-04: Added R030 untrusted-body delimiter handling so prompt payloads isolate email-body content and redact embedded delimiter tokens.
