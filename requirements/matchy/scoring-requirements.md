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
- R020-T06: Thousands separators are parsed and matched at integer-cents precision (`tests/py/test_scoring_core.py`).
- R020-T07: Integer tokens do not match non-whole amounts when cents differ (`tests/py/test_scoring_core.py`).

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

R040  Statement: `relevance_tokens` extracts long tokens for corpus relevance statistics.
Design: Reuse `normalized_text`, split on whitespace, and keep tokens longer than two characters while preserving order and repeats so term frequencies are accurate.
Tests:
- R040-T01: Long tokens are kept in order including repeats (`tests/py/test_scoring_core.py`).
- R040-T02: Short tokens are dropped, leaving an empty list when none qualify (`tests/py/test_scoring_core.py`).

R045  Statement: `subset_sum_reachable` reports whether a non-empty subset of positive integer-cent amounts lands within tolerance of the target.
Design: Maintain a reachable-sum set seeded with zero, extend it per positive amount while pruning sums above the upper bound, and report success when any non-zero reachable sum falls inside the inclusive `[target-tolerance, target+tolerance]` band.
Tests:
- R045-T01: A subset summing exactly to the target is reachable (`tests/py/test_scoring_core.py`).
- R045-T02: No in-bound subset (and overshoot pruning) yields False (`tests/py/test_scoring_core.py`).
- R045-T03: Sums inside the tolerance band match and values beyond it are excluded (`tests/py/test_scoring_core.py`).
- R045-T04: Non-positive amounts are ignored and a zero subset never satisfies the target (`tests/py/test_scoring_core.py`).
- R045-T05: One-cent amounts participate in subset sums (boundary strictly above zero) (`tests/py/test_scoring_core.py`).

R041  Statement: `document_frequencies` counts how many corpus documents contain each long token.
Design: For each document, deduplicate its long tokens with a set and increment a per-token document counter so frequency reflects document presence rather than raw occurrences.
Tests:
- R041-T01: Document frequency counts documents containing each token (`tests/py/test_scoring_core.py`).
- R041-T02: An empty corpus yields no frequencies (`tests/py/test_scoring_core.py`).

R042  Statement: `inverse_document_frequency` returns the smoothed BM25 idf for a token.
Design: Compute `log(1 + (corpus_size - document_frequency + 0.5) / (document_frequency + 0.5))` so rarer tokens score higher and the value stays non-negative.
Tests:
- R042-T01: Closed-form idf values match for known corpus statistics (`tests/py/test_scoring_core.py`).
- R042-T02: Rarer tokens receive strictly higher idf (`tests/py/test_scoring_core.py`).

R043  Statement: `bm25_score` computes Okapi BM25 relevance of a query against a document.
Design: Accumulate per-query-token contributions using term frequency, idf, the `k1` saturation term, and `b` length normalization against the average document length; return zero for empty documents or empty corpora.
Tests:
- R043-T01: Closed-form BM25 value matches while exercising tf, idf, k1, and b (`tests/py/test_scoring_core.py`).
- R043-T02: A query token absent from the document contributes nothing (`tests/py/test_scoring_core.py`).
- R043-T03: Empty document or empty corpus yields zero relevance (`tests/py/test_scoring_core.py`).
- R043-T04: A below-one average document length drives the b length-normalization term (`tests/py/test_scoring_core.py`).
- R043-T05: A zero average document length falls back to neutral normalization without dividing by zero (`tests/py/test_scoring_core.py`).
- R043-T06: Length-one documents and single-document corpora still produce relevance (`tests/py/test_scoring_core.py`).
- R043-T07: A query token absent from the frequency map is treated as document frequency zero (`tests/py/test_scoring_core.py`).
- R043-T08: Relevance sums the contribution of every distinct matching query token (`tests/py/test_scoring_core.py`).

R044  Statement: `bm25_relevance` saturates a raw BM25 score into the unit interval.
Design: Map non-negative scores via `score / (score + saturation)` and collapse non-positive scores or non-positive saturation to zero.
Tests:
- R044-T01: Saturation maps raw scores into `[0, 1)` (`tests/py/test_scoring_core.py`).
- R044-T02: Non-positive score or saturation collapses to zero (`tests/py/test_scoring_core.py`).
- R044-T03: A saturation at or below one still scales rather than collapsing to zero (`tests/py/test_scoring_core.py`).

R046  Statement: `amount_reconciliation_score` fires when the transaction total equals a subset of smaller candidate amounts.
Design: Extract candidate money amounts, retain only those strictly below the target so any reaching subset uses two or more items, cap the term count to bound the DP, and return `1.0` when `subset_sum_reachable` succeeds; this is distinct from single-token `amount_hint_score`.
Tests:
- R046-T01: A subset of line items summing to the total yields one (`tests/py/test_scoring_core.py`).
- R046-T02: A single token equal to the total is excluded from reconciliation (`tests/py/test_scoring_core.py`).
- R046-T03: Non-reaching, empty, and zero-target inputs yield zero (`tests/py/test_scoring_core.py`).
- R046-T04: One-cent line items are retained and can complete a reconciling subset (`tests/py/test_scoring_core.py`).

R047  Statement: `rank_candidates` blends BM25 relevance and amount reconciliation into the weighted score with a stable reason key set.
Design: Build the candidate corpus once, compute document frequencies and average document length, score each candidate's BM25 relevance and subset-sum reconciliation, add them to the clamped weighted sum, and always emit `bm25_relevance` and `amount_reconciliation` reason keys.
Tests:
- R047-T01: Ranked candidates expose bounded BM25 and reconciliation reason keys (`tests/py/test_scoring.py`).
- R047-T02: A candidate sharing a distinctive merchant token outranks an unrelated one (`tests/py/test_scoring.py`).
- R047-T03: Subset-sum reconciliation lifts a multi-item receipt totaling the transaction amount (`tests/py/test_scoring.py`).

## Changelog

- 2026-05-20: Added scoring_core contract requirements R010–R035 with unit-test traceability.
- 2026-05-18: Added scoring requirements coverage for normalization and rank ordering.
- 2026-05-29: Added R020-T06 (thousands separators) and R020-T07 (integer vs non-whole cents) test cases.
