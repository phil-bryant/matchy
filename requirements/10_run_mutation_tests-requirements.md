# Run Mutation Tests Requirements

## Scope

Applies to `10_run_mutation_tests.sh`.

R001  Statement: Run in strict fail-fast mode from repository root.
Design: Use `umask 007`, `set -euo pipefail`, and resolve `SCRIPT_DIR` for path-independent execution.
Tests:
- R001-T01: Run from a non-repo working directory and verify execution succeeds.

R005  Statement: Fail fast when required commands are unavailable.
Design: Verify `matchy-venv/bin/python` exists and `python -m mutmut` is importable before mutation testing begins. Emit guidance referencing `./02_create_venv.sh` and `./03_load_requirements.sh` on failure.
Tests:
- R005-T01: Run without venv python and verify explicit non-zero failure output with setup guidance.
- R005-T02: Run with venv python but without mutmut and verify explicit non-zero failure output.

R010  Statement: Require unit tests to pass before mutation testing begins.
Design: By default skip the pytest preflight (`MUTATION_SKIP_PREFLIGHT` defaults to `true`) and assume `./05_run_unit_tests.sh` already passed. When `MUTATION_SKIP_PREFLIGHT=false`, run `python -m pytest tests/py -q` before mutmut (pytest only; does not invoke Bats). If pytest fails, abort with guidance to run `./05_run_unit_tests.sh`.
Tests:
- R010-T01: Force pytest failure with `MUTATION_SKIP_PREFLIGHT=false` and verify script exits non-zero with guidance to run step-05 first.
- R010-T02: Verify mutmut is not invoked when preflight pytest fails.
- R010-T03: Run with default settings and verify pytest is not invoked while mutmut still runs.

R015  Statement: Run mutmut mutation testing across configured Matchy modules.
Design: Invoke `python -m mutmut run` from the repository root with `PATH` including `matchy-venv/bin`, then `python -m mutmut export-cicd-stats`. Copy `mutants/mutmut-cicd-stats.json` to `${REPORT_DIR}/mutmut-cicd-stats.json`. If no stats JSON is written, fail loudly with captured output rather than reporting `0.0%`.
Tests:
- R015-T01: Verify `mutmut run` is invoked from the repository root after preflight passes.
- R015-T02: Verify mutmut CI/CD stats JSON is written under `${REPORT_DIR}`.
- R015-T03: Simulate mutmut finishing without writing stats JSON and verify the script fails with diagnostics.

R020  Statement: Gate on a configurable minimum mutation score threshold.
Design: Read killed/survived counts from mutmut CI/CD stats. Compute score as `killed / (killed + survived) * 100`. Compare against `MUTATION_SCORE_THRESHOLD` (default `90`). Fail when the score is below the threshold or when no killed/survived verdicts exist.
Tests:
- R020-T01: Simulate stats with score below threshold and verify explicit non-zero failure.
- R020-T02: Simulate stats with score at or above threshold and verify pass.
- R020-T03: Verify custom `MUTATION_SCORE_THRESHOLD` environment variable overrides the default.

R022  Statement: Gate on a configurable minimum mutator coverage threshold.
Design: Compute mutator coverage as `(killed + survived) / total * 100`. Compare against `MUTATOR_COVERAGE_THRESHOLD` (default `70`). Fail when coverage is below the threshold, even if the score is above its threshold.
Tests:
- R022-T01: Simulate stats with coverage below threshold (and score above) and verify explicit non-zero failure citing mutator coverage.
- R022-T02: Simulate stats with coverage at or above threshold and verify pass.
- R022-T03: Verify custom `MUTATOR_COVERAGE_THRESHOLD` environment variable overrides the default.

R025  Statement: Support recording file-level exclusions in the mutation summary.
Design: Accept `MUTATION_EXCLUDE_FILES` as a comma-separated list for the persisted summary `excluded_files` field. Primary exclusions are configured in `pyproject.toml` `do_not_mutate`.
Tests:
- R025-T01: Set `MUTATION_EXCLUDE_FILES` and verify values appear in `mutation-summary.json`.
- R025-T02: Verify default (empty) exclusion list records an empty array.

R030  Statement: Persist machine-readable mutation testing report.
Design: Write a normalized summary to `${REPORT_DIR}/mutation-summary.json` containing at minimum: `total`, `killed`, `survived`, `skipped`, `timed_out`, `score`, `mutator_coverage`, thresholds, `score_failed`, `coverage_failed`, `gate_failed`, and `by_module`.
Tests:
- R030-T01: Verify `${REPORT_DIR}/mutation-summary.json` is written after a successful run.
- R030-T02: Verify the JSON contains required fields.

R035  Statement: Emit concise operator-readable pass or fail output.
Design: Print one `✅ PASS:` line with score and coverage when the gate passes. Print `❌ FAIL:` lines when gates fail.
Tests:
- R035-T01: Verify successful run emits a single `✅ PASS:` line including the score.
- R035-T02: Verify failed run emits `❌ FAIL:` lines including score and/or coverage thresholds.

R040  Statement: Support a timeout to prevent runaway mutation runs.
Design: Accept `MUTATION_TIMEOUT_SECONDS` (default `600`). Kill mutmut if it exceeds the timeout and fail with a timeout-specific message.
Tests:
- R040-T01: Simulate mutmut exceeding timeout and verify explicit timeout failure message.
- R040-T02: Verify default timeout is 600 seconds when not overridden.

R045  Statement: Mutation pytest scope includes scoring_core contract tests.
Design: Configure `pyproject.toml` `tool.mutmut.tests_dir` to include `tests/py/test_scoring_core.py` whenever `matchy/scoring_core.py` is in `only_mutate`, so mutmut evaluates scoring helpers against direct behavioral tests (not only `rank_candidates` integration tests).
Tests:
- R045-T01: Verify `tests/py/test_scoring_core.py` is listed in `tool.mutmut.tests_dir`.
- R045-T02: Verify mutmut stats map `scoring_core` functions to tests under `test_scoring_core.py`.

## Changelog

- 2026-05-20: Raised default mutation score threshold to 90% and required scoring_core contract tests in mutmut scope (R045).
- 2026-05-20: Initial requirements for Python mutation testing gate (step-10).
