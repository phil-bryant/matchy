# Run Matchy Driver Requirements

## Scope

Applies to `09_run_matchy_driver.py`.

R001  Statement: Provide executable Python entrypoint for pending-match driver runs.
Design: Script starts with Python shebang and enters a loop function from `__main__`.
Tests:
- R001-T01: Execute script in one-shot mode and verify it calls pending-run endpoint once.

R005  Statement: Post deterministic pending-run payload values with env-var overrides.
Design: Driver posts JSON body with `limit`, `lookback_days`, and `trigger_source`; interval/timeout/loop behavior are env-configurable.
Tests:
- R005-T01: Stub HTTP client and verify posted URL and payload fields match configured values.

R010  Statement: Driver startup profiling logs are opt-in via CLI flag.
Design: Startup profiling lines are disabled by default; passing `--profile` enables startup timing output.
Tests:
- R010-T01: Run without `--profile` and verify startup profiling lines are absent.
- R010-T02: Run with `--profile` and verify startup profiling lines are emitted.
- R010-T03: Run with `--profile` and a delayed pending-run response, then verify in-flight wait heartbeat logs are emitted.

## Changelog

- 2026-05-18: Added requirements for `09_run_matchy_driver.py` to automate pending transaction matching runs.
- 2026-05-24: Added opt-in `--profile` requirement for driver startup timing logs.
