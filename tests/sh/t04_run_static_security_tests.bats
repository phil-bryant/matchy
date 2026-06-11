#!/usr/bin/env bats
# Thin pointer contract tests for tests/t04_run_static_security_tests.sh.
# Fully offline: they inspect the pointer's wiring text only and never execute the delegated lane.

#R001: Bats setup resolves repo root and pointer path for offline pointer-contract tests.
setup() {
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd -P)"
  POINTER="${REPO_ROOT}/tests/t04_run_static_security_tests.sh"
}

@test "sources the shared pointer shim for umask/strict mode" {
  #R001-T01: the pointer sources pointer_shim.sh (centralized umask 007 + set -euo pipefail).
  run grep -F "pointer_shim.sh" "$POINTER"
  [ "$status" -eq 0 ]
}

@test "resolves the shim from the runner src/scripts tree" {
  #R005-T01: the pointer locates the shim under runner/src/scripts (RUNNER_HOME/repo-root resolution).
  run grep -F "runner/src/scripts" "$POINTER"
  [ "$status" -eq 0 ]
}

@test "selects the matchy runbook profile before delegation" {
  #R010-T01: the pointer sets RUNBOOK_PROFILE to matchy so the shim sources the matchy profile.
  run grep -F 'RUNBOOK_PROFILE="matchy"' "$POINTER"
  [ "$status" -eq 0 ]
}

@test "delegates to the mapped runner golden with argument passthrough" {
  #R015-T01: the pointer calls delegate_golden for the mapped golden with argument passthrough.
  run grep -F 'delegate_golden "tests/t03_run_static_security_tests.sh" "$@"' "$POINTER"
  [ "$status" -eq 0 ]
}
