# Matchy Scoring Requirements

## Scope

Applies to `matchy/scoring.py`.

R001  Statement: Normalize text for token overlap scoring.
Design: Lowercase and strip non-alphanumeric characters before tokenization so overlap scoring is punctuation-insensitive.
Tests:
- R001-T01: Rank candidates where punctuation differs and verify normalized matching still contributes score.

R005  Statement: Return ranked candidates sorted by descending weighted score.
Design: Compute weighted heuristic scores and return rows sorted from highest to lowest score.
Tests:
- R005-T01: Rank two candidates with distinct evidence and verify output order is descending by score.

## Changelog

- 2026-05-18: Added scoring requirements coverage for normalization and rank ordering.
