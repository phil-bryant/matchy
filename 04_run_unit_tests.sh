#!/bin/bash
umask 007
#R001: Enforce strict fail-fast behavior.
set -euo pipefail

#R010: Resolve repository root from script location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

#R005: Require bats before test execution.
if ! command -v bats >/dev/null 2>&1; then
  echo "bats is required but was not found on PATH."
  exit 1
fi

#R015: Discover Bats files from testing lanes.
shopt -s nullglob
BATS_TEST_FILES=( "${REPO_ROOT}"/testing/*.bats "${REPO_ROOT}"/testing/sh/*.bats )
shopt -u nullglob

#R020: Fail clearly when no tests are discovered.
if [ "${#BATS_TEST_FILES[@]}" -eq 0 ]; then
  echo "No shell unit tests found under ${REPO_ROOT}/testing."
  exit 1
fi

#R025: Execute discovered tests and fail on non-zero result.
if ! (
  cd "$REPO_ROOT"
  bats "${BATS_TEST_FILES[@]}"
); then
  echo "Shell unit tests failed."
  exit 1
fi

#R030: Emit single pass line on successful completion.
echo "✅ PASS: Matchy unit tests completed."
