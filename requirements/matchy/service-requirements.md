# Matchy Service Requirements

## Scope

Applies to `matchy/service.py`.

R001  Statement: Fail early when transaction IDs are unknown.
Design: Raise `ValueError` when repository transaction lookup returns no row before candidate retrieval.
Tests:
- R001-T01: Stub repository transaction lookup to return none and verify `match_transaction` raises `ValueError`.

R005  Statement: Build deterministic normalized search queries from transaction text.
Design: Normalize description/counterparty text to lowercase alphanumeric tokens, drop short/numeric tokens, and select deterministic token subsets.
Tests:
- R005-T01: Call `_build_query` and `_build_broad_query` with noisy text and verify normalized deterministic outputs.

## Changelog

- 2026-05-18: Added service requirements coverage for missing transaction and query construction behavior.
