# Run Fuzz Tests Requirements

## Scope

Applies to `11_run_fuzz.sh`.

R001  Statement: Run fuzz tests in strict fail-fast mode from repository root.
Design: Use `set -euo pipefail`, resolve script directory, and execute pytest with Hypothesis-backed property tests.
Tests:
- R001-T01: Run from non-repo cwd and verify fuzz invocation still targets repository tests.

R005  Statement: Fail fast when venv python or hypothesis is unavailable.
Design: Print actionable error when `matchy-venv/bin/python` or the `hypothesis` package is missing.
Tests:
- R005-T01: Run without venv python and verify non-zero failure.
- R005-T02: Run without hypothesis installed and verify non-zero failure.

R010  Statement: Fuzz scoring property tests with a configurable example budget.
Design: Default `FUZZ_TEST_PATHS` to `tests/py/test_scoring_properties.py`, `FUZZ_MAX_EXAMPLES` to `500`, and `FUZZ_DEADLINE_MS` to `1000`. Pass `HYPOTHESIS_MAX_EXAMPLES` and `HYPOTHESIS_DEADLINE` into pytest. Run with `-p hypothesis` and `--hypothesis-show-statistics`.
Tests:
- R010-T01: Run with pytest stub and verify fuzz paths, Hypothesis env vars, and statistics flag appear in invocation log.

R015  Statement: Emit concise success output and persist a fuzz summary report.
Design: Write `${REPORT_DIR}/fuzz-summary.json` with property test names and example counters. Print `✅ PASS:` when gates succeed.
Tests:
- R015-T01: Run successful fuzz stub path and verify pass output line.
- R015-T02: Verify fuzz summary JSON is written under `${REPORT_DIR}`.

R020  Statement: Gate on pytest failures and minimum fuzz example budget.
Design: Parse Hypothesis statistics from pytest output. Require at least `FUZZ_MIN_PROPERTY_TESTS` (default `12`) property tests and `FUZZ_MIN_TOTAL_EXAMPLES` total passing examples (default `80%` of `FUZZ_MIN_PROPERTY_TESTS * FUZZ_MAX_EXAMPLES`). Fail when pytest exits non-zero, the lane times out, or the budget is not met.
Tests:
- R020-T01: Simulate statistics below the example budget and verify explicit non-zero failure.
- R020-T02: Simulate statistics at or above the example budget with pytest success and verify pass.
- R020-T03: Simulate pytest failure and verify non-zero failure even when statistics are present.

R025  Statement: Enforce a configurable fuzz lane timeout.
Design: Wrap pytest execution with `FUZZ_TIMEOUT_SECONDS` (default `300`) and fail with diagnostics on timeout exit `124`.
Tests:
- R025-T01: Simulate timeout exit code and verify explicit non-zero failure output.

R030  Statement: Fuzz scoring helpers with semantic properties beyond simple bounds.
Design: Property tests in `tests/py/test_scoring_properties.py` MUST assert normalization charset rules and exact `time_proximity_score` bucket outputs for documented hour deltas, not only score range invariants.
Tests:
- R030-T01: Verify fuzz suite includes normalization charset and time-bucket semantic property tests.

## Changelog

- 2026-05-20: Added R030 semantic scoring property requirements for normalization and time buckets.
- 2026-05-20: Strengthen fuzz lane with example-budget gate, summary report, and expanded scoring properties.
- 2026-05-20: Initial requirements for Hypothesis property-based fuzz lane (step-11).
