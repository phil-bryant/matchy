# Run Unit Tests Requirements

## Scope

Applies to `04_run_unit_tests.sh`.

R001  Statement: Run with `bash` in strict fail-fast mode.
Design: Use `set -euo pipefail` so failures stop execution immediately.
Tests:
- Introduce a failing command and verify the script exits non-zero.

R005  Statement: Refuse shell-test execution when Bats is unavailable.
Design: Require `bats` on `PATH` before test invocation.
Tests:
 - Run with `bats` unavailable and verify explicit non-zero failure output.

R010  Statement: Resolve execution root from script location rather than caller working directory.
Design: Derive repository root from the script directory and run tests from that location.
Tests:
- Invoke script from a different current working directory and verify tests still run against the repository root.

R015  Statement: Discover Matchy shell tests from `testing/` lanes.
Design: Discover `.bats` files from both `testing/*.bats` and `testing/sh/*.bats`.
Tests:
 - Run with no discovered test files and verify explicit non-zero failure output.
 - Run with one or more discovered test files and verify invocation proceeds.

R020  Statement: Execute all discovered Bats files in one lane.
Design: Invoke `bats` with all discovered test files.
Tests:
 - Verify `bats` receives all discovered files.

R025  Statement: Fail clearly when Bats execution fails.
Design: If `bats` returns non-zero, print failure output and exit non-zero.
Tests:
 - Stub `bats` to fail and verify non-zero exit with clear message.

R030  Statement: Emit concise operator-readable pass output.
Design: Print a single `✅ PASS:` line only after all unit-test checks succeed.
Tests:
- Verify successful run emits exactly one `✅ PASS:` line.

## Changelog

- 2026-05-12: Reswizzled from copied Swift+Tests contract to Matchy Bats-based `testing/` lanes.
