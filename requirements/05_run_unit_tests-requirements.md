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

R015  Statement: Discover Matchy shell automation tests from numbered `testing/sh` lanes.
Design: Discover `.bats` files from `testing/sh/` when the basename starts with `NN_` or equals `.gitignore.bats`.
Tests:
- R015-T01: Run with no discovered shell test files and verify explicit non-zero failure output.
- R015-T02: Run with one or more discovered shell test files and verify Bats invocation proceeds after pytest.

R020  Statement: Execute all discovered shell Bats files in one lane.
Design: Invoke `bats` with all discovered shell automation test files.
Tests:
- R020-T01: Verify `bats` receives all discovered shell test files.

R025  Statement: Fail clearly when Bats execution fails.
Design: If `bats` returns non-zero, print failure output and exit non-zero.
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
Design: Invoke `"${REPO_ROOT}/matchy-venv/bin/python" -m pytest "${REPO_ROOT}/testing/py"` with `PYTHONPATH` set to the repository root.
Tests:
- R040-T01: Verify pytest runs against `testing/py` before Bats shell tests execute.

R045  Statement: Fail clearly when pytest execution fails.
Design: If pytest returns non-zero, print failure output and exit non-zero before shell tests run.
Tests:
- R045-T01: Stub pytest to fail and verify non-zero exit with clear message.

## Changelog

- 2026-05-19: Added pytest stage for `testing/py` and limited Bats discovery to numbered shell automation specs.
- 2026-05-12: Reswizzled from copied Swift+Tests contract to Matchy Bats-based `testing/` lanes.
