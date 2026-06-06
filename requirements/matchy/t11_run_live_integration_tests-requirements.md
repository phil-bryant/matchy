# Matchy Live Integration Lane Requirements

## Scope

Applies to `tests/t11_run_live_integration_tests.sh`. A thin, opt-in LIVE integration lane that
exercises the real api -> service -> repository path against a live Teller Postgres DB and a live
Mailcart endpoint. It complements (does not replace) the offline unit lanes and the eggnest-root
golden replay. Its end-to-end payload lives in `tests/integration/` so the offline unit lane never
collects it.

R001  Statement: Soft-pass with a clear skip message when live dependencies are absent.
Design: The lane prints an explicit `SKIP (live integration): ...` line and exits 0 whenever the live Teller DB / Mailcart dependencies are not present, so it never turns the default offline suite red and never reports a false green (no faked pass).
Tests:
- R001-T01: Running the lane with no live dependencies prints a SKIP message and exits 0.

R005  Statement: Probe both dependencies and name whichever is unavailable.
Design: The lane probes Mailcart `/health` (curl, TLS, short timeout) and the Teller DB (TELLER_DB_PASSWORD plus a TCP connect to host:port) and lists each missing dependency by name in the skip message instead of erroring deep inside pytest.
Tests:
- R005-T01: With the opt-in enabled but dependencies unreachable, the skip message names the missing Mailcart and/or Teller DB dependency and exits 0.

R010  Statement: Gate live execution behind an explicit opt-in and run the end-to-end match scenario only when enabled and reachable.
Design: Live execution requires `MATCHY_LIVE_INTEGRATION=true`; without it the lane never reaches Postgres/Mailcart and never invokes the integration module. When enabled and both dependencies are reachable, the lane runs `pytest tests/integration`, which constructs a real `MatchService` and asserts persisted match results.
Tests:
- R010-T01: Without the opt-in the lane reports the opt-in is disabled, does not invoke the live integration module, and exits 0.

## Changelog

- 2026-06-05: Added the opt-in, dependency-probed live integration lane (t11) for matchy with soft-pass skip behavior.
