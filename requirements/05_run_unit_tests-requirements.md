# Run Unit Tests Requirements

## Scope

Applies to `05_run_unit_tests.sh`.

R001  Statement: Run with `bash` in strict fail-fast mode.
Design: Use `set -euo pipefail` so failures stop execution immediately.
Tests:
- R001-T01: Introduce a failing command and verify the script exits non-zero.

R005  Statement: Refuse shell-test execution when Bats is unavailable.
Design: Require `bats` on `PATH` before shell test invocation.
Tests:
- R005-T01: Run with `bats` unavailable and verify explicit non-zero failure output.

R010  Statement: Resolve execution root from script location rather than caller working directory.
Design: Derive repository root from the script directory and run tests from that location.
Tests:
- R010-T01: Invoke script from a different current working directory and verify tests still run against the repository root.

R015  Statement: Discover Matchy shell automation tests from numbered `tests/sh` lanes.
Design: Discover `.bats` files from `tests/sh/` when the basename starts with `NN_` or equals `.gitignore.bats`.
Tests:
- R015-T01: Run with no discovered shell test files and verify explicit non-zero failure output.
- R015-T02: Run with one or more discovered shell test files and verify Bats invocation proceeds after pytest.

R020  Statement: Refuse shell-test execution when the bats test directory is missing.
Design: Verify `tests/sh` exists before discovery; fail fast with an actionable path when absent.
Tests:
- R020-T01: Remove `tests/sh` in fixture and verify explicit non-zero failure output.

R025  Statement: Fail clearly when parallel Bats execution fails.
Design: If any per-file bats invocation returns non-zero, print failure output and exit non-zero.
Tests:
- R025-T01: Stub `bats` to fail and verify non-zero exit with clear message.

R030  Statement: Emit concise operator-readable pass output.
Design: Print a single `✅ PASS:` line only after Python and shell unit-test checks succeed.
Tests:
- R030-T01: Verify successful run emits exactly one `✅ PASS:` line.

R035  Statement: Require matchy-venv python and pytest before Python test execution.
Design: Resolve `${REPO_ROOT}/matchy-venv/bin/python`, verify `python -m pytest --version`, and fail with setup guidance when either is missing.
Tests:
- R035-T01: Run without venv python and verify explicit non-zero failure output.
- R035-T02: Run with venv python but without pytest and verify explicit non-zero failure output.

R040  Statement: Run pytest against the Python application test lane before shell tests.
Design: Invoke `"${REPO_ROOT}/matchy-venv/bin/python" -m pytest "${REPO_ROOT}/tests/py"` with `PYTHONPATH` set to the repository root.
Tests:
- R040-T01: Verify pytest runs against `tests/py` before Bats shell tests execute.

R045  Statement: Fail clearly when pytest execution fails.
Design: If pytest returns non-zero, print failure output and exit non-zero before shell tests run.
Tests:
- R045-T01: Stub pytest to fail and verify non-zero exit with clear message.

R050  Statement: Run discovered bats files in parallel by file with buffered per-file output, configurable via `BATS_JOBS`, `BATS_JOBS_CAP`, `PARALLEL_LANES`, `BATS_FILTER`, `BATS_FILTER_STATUS`, and `BATS_USE_NATIVE_JOBS`.
Design: Discover numbered `tests/sh/*.bats` files (`NN_` prefix or `.gitignore.bats`); fail fast when the directory is missing or no files match. Run `12_*.bats` serially after the parallel batch: script-12 meta-runner self-tests spawn nested parallel orchestrators. `06_run_security_checks_*.bats` files run in the parallel batch (stubbed scanners, lane subsets, and foreground detect-secrets in tests). Default mode invokes each parallel-lane file via `xargs -0 -P "$BATS_JOBS_RESOLVED"`, calling `bats --tap --print-output-on-failure --timing <file>` so per-test result lines, failure diagnostics, and per-test timings remain visible. Print `===== <basename> (running) =====` before each file starts and `===== <basename> =====` with buffered output when it finishes. Each file's stdout/stderr is buffered to a tempfile under `$(mktemp -d)`; the tempdir is cleaned up via `trap EXIT` (moved to Trash, never `rm`). When `BATS_USE_NATIVE_JOBS=true` and GNU `parallel` is on PATH, invoke `bats -j` on the parallel file set; when parallel is unavailable print a fallback notice and revert to the xargs path. Default concurrency is `sysctl -n hw.ncpu` capped by `BATS_JOBS_CAP` (default 8); when `PARALLEL_LANES` is set and > 1 (outer `12_run_all_checks_parallel.sh`), divide the default by `PARALLEL_LANES` (floor 1). `BATS_JOBS` overrides the resolved default. `BATS_FILTER` forwards as `-f <value>` and `BATS_FILTER_STATUS` as `--filter-status <value>` to every bats invocation.
Tests:
- R050-T01: Verify parallel bats invocation forwards `--tap`, `--print-output-on-failure`, and `--timing` per file.
- R050-T02: Empty discovered set verifies the runner fails fast with a clear message.
- R050-T03: Missing `tests/sh` directory verifies the runner fails fast with a clear message.
- R050-T04: `BATS_JOBS=1` verifies the resolved-jobs value flows through to the progress banner.
- R050-T05: `PARALLEL_LANES=99` with `BATS_JOBS` unset clamps the default to 1 so an outer meta-runner does not oversubscribe.
- R050-T06: `BATS_FILTER=foo` verifies `-f foo` is forwarded to every bats call.
- R050-T07: `BATS_FILTER_STATUS=failed` verifies `--filter-status failed` is forwarded to every bats call.
- R050-T08: Verify the per-file output dump is prefixed by `===== <basename> =====`.
- R050-T09: A failing bats stub verifies the meta-runner exits non-zero.
- R050-T10: `BATS_USE_NATIVE_JOBS=true` with no `parallel` on PATH verifies the runner prints a fallback notice and still runs the xargs path successfully.
- R050-T11: `BATS_USE_NATIVE_JOBS=true` with a stub `parallel` on PATH verifies bats is invoked once with `-j` and the discovered file list (not once per file).

## Changelog

- 2026-05-20: `06_run_security_checks_*.bats` moved to parallel batch; serial lane is `12_*.bats` only.
- 2026-05-20: Added `R050` parallel-by-file bats runner; serial lane for `12_run_all_checks_parallel.bats`, `BATS_JOBS_CAP`, and running banners (ported from valve `05_run_unit_tests.sh`).
- 2026-05-20: Renamed repository test directory from `testing/` to `tests/`.
- 2026-05-19: Added pytest stage for `tests/py` and limited Bats discovery to numbered shell automation specs.
- 2026-05-12: Reswizzled from copied Swift+Tests contract to Matchy Bats-based `tests/` lanes.
