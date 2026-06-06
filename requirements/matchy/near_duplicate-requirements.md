# Matchy Near-Duplicate Requirements

## Scope

Applies to `matchy/near_duplicate.py`. Provides the SimHash helpers (`_simhash64`, `_hamming_distance`)
and `NearDuplicateMixin`, the near-duplicate collapsing concern extracted from the service
orchestration module. Mixed into `MatchService` and invoked in `match_transaction` after body
enrichment.

R055  Statement: Collapse near-duplicate candidate emails (forwarded or marketing variants of the same receipt) using SimHash fingerprints under a Hamming-distance threshold.
Design: `_simhash64` builds a 64-bit fingerprint from a candidate's long tokens using keyed BLAKE2b per-bit voting; `_hamming_distance` counts differing bits. `_collapse_near_duplicates` keeps the first representative of each cluster, never collapses contentless (zero) fingerprints, and is a no-op for a non-positive threshold or trivial input. `_near_duplicate_max_distance` resolves the threshold from `near_duplicate_max_hamming_distance`, defaulting to 0 (disabled) and rejecting non-positive/invalid values. Collapsing runs after body enrichment so similarity is judged on full bodies.
Tests:
- R055-T01: SimHash is deterministic, zero for empty text, and far in Hamming distance for unrelated text.
- R055-T02: Hamming distance counts differing bits and is zero for equal fingerprints.
- R055-T03: Identical bodies collapse to the first representative, distinct content survives, and disabled/trivial input is unchanged.
- R055-T04: The distance resolver defaults to disabled, honors positive values, and rejects invalid input.

## Changelog

- 2026-06-05: Extracted R055 (SimHash near-duplicate collapsing) from `service.py` into `near_duplicate.py`/`NearDuplicateMixin`.
