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

R010  Statement: Run pending unmatched transactions in batch using repository discovery.
Design: Load pending transaction ids from repository lookback query and invoke `match_transaction` for each id with requested trigger source.
Tests:
- R010-T01: Stub pending id discovery and verify `match_pending_transactions` delegates each id to `match_transaction`.

## Changelog

- 2026-05-18: Added service requirements coverage for missing transaction and query construction behavior.
- 2026-05-18: Added R010 pending batch-matching requirements for driver orchestration.
