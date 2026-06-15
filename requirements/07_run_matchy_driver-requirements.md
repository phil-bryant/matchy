# Run Matchy Driver Requirements

## Scope

Applies to `07_run_matchy_driver.py`.

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

R015  Statement: Default the driver to the authoritative C++ matchycore runtime with an opt-in Python engine.
Design: `--engine {cpp,python}` (env `MATCHY_ENGINE`, default `cpp`) selects the runtime; `cpp` builds/execs `src/core/build/matchy_driver`, while `--engine python` runs the in-process requests loop for A/B testing.
Tests:
- R015-T01: Run with `--engine python` in one-shot mode and verify the in-process requests loop posts the pending run.

## Changelog

- 2026-05-18: Added requirements for `07_run_matchy_driver.py` to automate pending transaction matching runs.
- 2026-05-24: Added opt-in `--profile` requirement for driver startup timing logs.
- 2026-06-14: Added `--engine` cutover requirement defaulting to the C++ matchycore runtime with a Python fallback.
