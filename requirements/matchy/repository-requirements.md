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

## Changelog

- 2026-05-18: Added repository requirements for initialization guard and session lifecycle.
