# Matchy DB Target Requirements

## Scope

Applies to `matchy/db_target.py`: active-backend SQL adaptation so matchy follows the teller DB
profile chain (ADR-0006) and runs identically against PostgreSQL and SQLite/SQLCipher.

R030  Statement: Resolve the active backend target from the teller DB profile chain.
Design: `is_sqlite()` resolves once per process via `teller.teller_db_profile.resolve_profile().target == "sqlite"`; any resolution failure (missing teller package or profile) preserves postgres-era behavior by returning false.
Tests:
- R030-T01: Target detection returns false when profile resolution raises and true for sqlite profiles.

R035  Statement: Render owned-schema SQL against SQLite prefixed mirror tables.
Design: `sql_for_target` maps `matchy.<t>`/`classy.<t>` references to `teller.matchy_<t>`/`teller.classy_<t>` on the SQLite target (Postgres SQL passes through unchanged) and quotes the reserved word in `teller.transaction` as `teller."transaction"` for current SQLite parsers.
Tests:
- R035-T01: Owned-schema references rewrite to prefixed mirror tables on sqlite and pass through on postgres.
- R035-T02: `teller.transaction` references are quoted on the sqlite target.

R040  Statement: Provide backend-aware parameter fragments for jsonb and timestamp values.
Design: `jsonb_param` renders `CAST(:name AS jsonb)` on PostgreSQL and a plain bind on SQLite; `bind_timestamp` binds ISO `YYYY-MM-DD HH:MM:SS` text on SQLite (CURRENT_TIMESTAMP parity) and native datetimes on PostgreSQL; `as_datetime` normalizes date/timestamp column values read from either backend.
Tests:
- R040-T01: jsonb/timestamp fragments and datetime normalization vary correctly by target.

## Changelog

- 2026-06-12: Initial requirements for profile-driven dual-target SQL adaptation
  (extracted pattern from classy's `_sql_for_active_target`).
