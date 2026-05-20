# Matchy Scoring Requirements

## Scope

Applies to `matchy/scoring.py` and `matchy/scoring_core.py`.

R001  Statement: Normalize text for token overlap scoring.
Design: Lowercase and strip non-alphanumeric characters before tokenization so overlap scoring is punctuation-insensitive.
Tests:
- R001-T01: Rank candidates where punctuation differs and verify normalized matching still contributes score (`tests/py/test_scoring.py`).

R005  Statement: Return ranked candidates sorted by descending weighted score.
Design: Compute weighted heuristic scores and return rows sorted from highest to lowest score.
Tests:
- R005-T01: Rank two candidates with distinct evidence and verify output order is descending by score (`tests/py/test_scoring.py`).

R010  Statement: `normalized_text` lowercases input and replaces non-alphanumeric characters with spaces.
Design: Apply `str.lower()` then substitute `[^a-z0-9\s]` with a single space so token overlap is punctuation-insensitive.
Tests:
- R010-T01: Mixed-case input becomes lowercase (`tests/py/test_scoring_core.py`).
- R010-T02: Punctuation becomes spaced separators (`tests/py/test_scoring_core.py`).
- R010-T03: Digits and spaces are preserved (`tests/py/test_scoring_core.py`).
- R010-T04: Mixed merchant phrases normalize predictably (`tests/py/test_scoring_core.py`).

R015  Statement: `token_overlap` returns a bounded ratio using long tokens only.
Design: Tokenize normalized text, keep tokens with length greater than two, return intersection size divided by the larger token-set size; return zero when either side has no qualifying tokens.
Tests:
- R015-T01: Empty or whitespace-only input yields zero (`tests/py/test_scoring_core.py`).
- R015-T02: Length-two tokens are excluded (`tests/py/test_scoring_core.py`).
- R015-T03: Partial overlap returns an exact ratio (`tests/py/test_scoring_core.py`).
- R015-T04: Denominator uses the larger side (`tests/py/test_scoring_core.py`).
- R015-T05: One side without long tokens yields zero (`tests/py/test_scoring_core.py`).
- R015-T06: Length-two left tokens are excluded (`tests/py/test_scoring_core.py`).
- R015-T07: Length-two right tokens are excluded (`tests/py/test_scoring_core.py`).

R020  Statement: `amount_hint_score` detects common amount string forms in candidate text.
Design: Search normalized candidate text for two-decimal, absolute two-decimal, dollar-prefixed absolute, and integer absolute amount hints derived from the transaction amount; return `1.0` on first match else `0.0`.
Tests:
- R020-T01: Two-decimal hint match (`tests/py/test_scoring_core.py`).
- R020-T02: Absolute decimal hint match (`tests/py/test_scoring_core.py`).
- R020-T03: Dollar hint match (`tests/py/test_scoring_core.py`).
- R020-T04: Integer hint match (`tests/py/test_scoring_core.py`).
- R020-T05: Missing amount text yields zero (`tests/py/test_scoring_core.py`).

R025  Statement: `sender_hint_score` is a binary long-token overlap signal.
Design: Normalize transaction and sender text, require shared tokens longer than two characters, return `1.0` when overlap exists else `0.0`.
Tests:
- R025-T01: Shared long token yields one (`tests/py/test_scoring_core.py`).
- R025-T02: No overlap yields zero (`tests/py/test_scoring_core.py`).
- R025-T03: Short-token-only overlap yields zero (`tests/py/test_scoring_core.py`).
- R025-T04: Empty inputs yield zero (`tests/py/test_scoring_core.py`).
- R025-T05: Three-character transaction tokens count (`tests/py/test_scoring_core.py`).
- R025-T06: Three-character sender tokens count (`tests/py/test_scoring_core.py`).

R030  Statement: `compact_merchant_hint_score` matches long non-digit transaction tokens inside compact candidate text.
Design: Strip non-alphanumeric characters from candidate text, scan transaction tokens with length at least six that are not all digits, return `1.0` when any token is a substring of compact candidate text else `0.0`.
Tests:
- R030-T01: Empty candidate yields zero (`tests/py/test_scoring_core.py`).
- R030-T02: Embedded long token yields one (`tests/py/test_scoring_core.py`).
- R030-T03: Short tokens are ignored (`tests/py/test_scoring_core.py`).
- R030-T04: Digit-only long tokens are ignored (`tests/py/test_scoring_core.py`).
- R030-T05: No substring match yields zero (`tests/py/test_scoring_core.py`).
- R030-T06: Punctuation is stripped before compact matching (`tests/py/test_scoring_core.py`).
- R030-T07: Six-character transaction tokens match (`tests/py/test_scoring_core.py`).
- R030-T08: Five-character transaction tokens do not match (`tests/py/test_scoring_core.py`).

R035  Statement: `time_proximity_score` maps hour distance to documented proximity buckets.
Design: Use absolute hour delta between transaction and received timestamps; return `1.0` (<=6h), `0.85` (<=24h), `0.65` (<=72h), `0.3` (<=720h), else `0.1`.
Tests:
- R035-T01: Bucket edge hours return exact scores (`tests/py/test_scoring_core.py`).
- R035-T02: Negative time ordering still uses absolute delta (`tests/py/test_scoring_core.py`).

## Changelog

- 2026-05-20: Added scoring_core contract requirements R010–R035 with unit-test traceability.
- 2026-05-18: Added scoring requirements coverage for normalization and rank ordering.
