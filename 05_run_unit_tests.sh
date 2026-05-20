#!/bin/bash
umask 007
#R001: Enforce strict fail-fast behavior.
set -euo pipefail

#R010: Resolve repository root from script location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
PYTHON_BIN="${REPO_ROOT}/matchy-venv/bin/python"
PYTEST_DIR="${REPO_ROOT}/testing/py"

print_runner_header() {
  local runner_name="$1"
  local explainer_line_1="$2"
  local explainer_line_2="$3"
  local runner_url="$4"
  local border="+==============================================================================+"
  printf '%s\n' "$border"
  printf '| %-76s |\n' "Test Runner: ${runner_name}"
  printf '| %-76s |\n' "${explainer_line_1}"
  printf '| %-76s |\n' "${explainer_line_2}"
  printf '| %-76s |\n' "URL: ${runner_url}"
  printf '%s\n' "$border"
}

#R035: Require matchy-venv python before Python test execution.
if [ ! -x "$PYTHON_BIN" ]; then
  echo "matchy-venv python is required but was not found at ${PYTHON_BIN}."
  echo "Run ./02_create_venv.sh and ./03_load_requirements.sh first."
  exit 1
fi

#R035: Refuse Python test execution when pytest is unavailable in the venv.
if ! "$PYTHON_BIN" -m pytest --version >/dev/null 2>&1; then
  echo "pytest is required in matchy-venv but was not found."
  echo "Run ./03_load_requirements.sh to install test dependencies."
  exit 1
fi

#R040: Run pytest against the Python application test lane first.
print_runner_header \
  "pytest" \
  "Python native unit test runner for Matchy application modules." \
  "Executes testing/py test files before shell automation checks." \
  "https://docs.pytest.org/"
echo ""
echo "▶ Running Python unit tests..."
if ! (
  cd "$REPO_ROOT"
  PYTHONPATH="$REPO_ROOT" TELLER_DB_PASSWORD="pw" "$PYTHON_BIN" -m pytest "$PYTEST_DIR"
); then
  echo "Python unit tests failed."
  exit 1
fi

#R005: Require bats before shell-test execution.
if ! command -v bats >/dev/null 2>&1; then
  echo "bats is required but was not found on PATH."
  exit 1
fi

#R015: Discover shell automation tests from numbered testing/sh lanes.
shopt -s nullglob
BATS_TEST_FILES=()
for candidate in "${REPO_ROOT}"/testing/sh/*.bats; do
  base="$(basename "$candidate")"
  if [[ "$base" =~ ^[0-9]{2}_ ]] || [[ "$base" == ".gitignore.bats" ]]; then
    BATS_TEST_FILES+=("$candidate")
  fi
done
shopt -u nullglob

#R020: Fail clearly when no shell tests are discovered.
if [ "${#BATS_TEST_FILES[@]}" -eq 0 ]; then
  echo "No shell unit tests found under ${REPO_ROOT}/testing/sh."
  exit 1
fi

#R025: Execute discovered shell tests and fail on non-zero result.
print_runner_header \
  "Bats" \
  "Shell script test framework for repository automation scripts." \
  "Runs numbered testing/sh Bats specs to verify script behavior and contracts." \
  "https://bats-core.readthedocs.io/"
echo ""
echo "▶ Running Bats shell tests..."
if ! (
  cd "$REPO_ROOT"
  bats "${BATS_TEST_FILES[@]}"
); then
  echo "Shell unit tests failed."
  exit 1
fi

#R030: Emit single pass line on successful completion.
echo "✅ PASS: Python and shell unit tests completed."
