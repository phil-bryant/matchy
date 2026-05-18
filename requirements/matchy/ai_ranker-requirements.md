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

## Changelog

- 2026-05-18: Added AI ranker requirements and numbered test traceability.
