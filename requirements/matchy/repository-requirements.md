# Matchy Repository Requirements

## Scope

Applies to `matchy/repository.py`.

R001  Statement: Require Teller DB password before repository initialization.
Design: Reject initialization when `teller_db_password` is empty to prevent anonymous write attempts.
Tests:
- R001-T01: Initialize repository with empty password and verify runtime error.

R005  Statement: Commit successful sessions and rollback failed sessions.
Design: Session context manager commits after successful work, rolls back on exceptions, and always closes the session.
Tests:
- R005-T01: Use a fake session factory and verify commit on success and rollback on failure.

R010  Statement: Discover pending transaction ids from active-unmatched lookback query.
Design: Query teller transactions with no active match row within a configurable lookback window and return deterministic ordered ids.
Tests:
- R010-T01: Stub SQL execution rows and verify `list_pending_transaction_ids` returns the discovered transaction ids.

## Changelog

- 2026-05-18: Added repository requirements for initialization guard and session lifecycle.
- 2026-05-18: Added R010 pending transaction discovery requirements for batch match drivers.
