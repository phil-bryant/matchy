#!/bin/bash
umask 007
#R001: Enforce strict fail-fast behavior.
set -euo pipefail

#R010: Resolve repository root from script location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
PYTHON_BIN="${REPO_ROOT}/matchy-venv/bin/python"
PYTEST_DIR="${REPO_ROOT}/tests/py"

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
  "Executes tests/py test files before shell automation checks." \
  "https://docs.pytest.org/"
echo ""
echo "▶ Running Python unit tests..."
#R045: Fail clearly when pytest execution fails.
if ! (
  cd "$REPO_ROOT"
  PYTHONPATH="$REPO_ROOT" "$PYTHON_BIN" -m pytest "$PYTEST_DIR"
); then
  echo "Python unit tests failed."
  exit 1
fi

#R005: Require bats before shell-test execution.
if ! command -v bats >/dev/null 2>&1; then
  echo "bats is required but was not found on PATH."
  exit 1
fi

#R015: Discover shell automation tests from numbered tests/sh lanes.
BATS_DIR="${REPO_ROOT}/tests/sh"
if [ ! -d "$BATS_DIR" ]; then
  echo "❌ Bats test directory not found: $BATS_DIR"
  exit 1
fi
shopt -s nullglob
BATS_PARALLEL_FILES=()
BATS_SERIAL_FILES=()
for candidate in "${BATS_DIR}"/*.bats; do
  base="$(basename "$candidate")"
  if [[ "$base" =~ ^[0-9]{2}_ ]] || [[ "$base" == ".gitignore.bats" ]]; then
    if [[ "$base" =~ ^12_ ]]; then
      BATS_SERIAL_FILES+=("$candidate")
    else
      BATS_PARALLEL_FILES+=("$candidate")
    fi
  fi
done
shopt -u nullglob

#R020: Fail clearly when no shell tests are discovered.
bats_file_count=$(( ${#BATS_PARALLEL_FILES[@]} + ${#BATS_SERIAL_FILES[@]} ))
if [ "$bats_file_count" -eq 0 ]; then
  echo "No shell unit tests found under ${BATS_DIR}."
  exit 1
fi

#R050: Run discovered bats files in parallel by file with buffered per-file output,
# configurable via BATS_JOBS, PARALLEL_LANES, BATS_FILTER, BATS_FILTER_STATUS, and
# BATS_USE_NATIVE_JOBS. Default mode uses xargs -P; when BATS_USE_NATIVE_JOBS=true
# and GNU parallel is on PATH, delegate to bats -j. Default concurrency is hw.ncpu;
# when PARALLEL_LANES>1 (outer meta-runner), divide so total concurrency stays near hw.ncpu.
print_runner_header \
  "Bats" \
  "Shell script test framework for repository automation scripts." \
  "Runs numbered tests/sh Bats specs to verify script behavior and contracts." \
  "https://bats-core.readthedocs.io/"
echo ""

bats_default_jobs="$(sysctl -n hw.ncpu 2>/dev/null || echo 8)"
if [[ "${PARALLEL_LANES:-1}" =~ ^[0-9]+$ ]] && [ "${PARALLEL_LANES:-1}" -gt 1 ]; then
  bats_default_jobs=$(( bats_default_jobs / PARALLEL_LANES ))
  [ "$bats_default_jobs" -lt 1 ] && bats_default_jobs=1
fi
BATS_JOBS_RESOLVED="${BATS_JOBS:-$bats_default_jobs}"
BATS_JOBS_CAP="${BATS_JOBS_CAP:-8}"
if [[ "${BATS_JOBS_CAP}" =~ ^[0-9]+$ ]] && [ "${BATS_JOBS_CAP}" -gt 0 ] && [ "$BATS_JOBS_RESOLVED" -gt "$BATS_JOBS_CAP" ]; then
  BATS_JOBS_RESOLVED="$BATS_JOBS_CAP"
fi

BATS_TMP_DIR="$(mktemp -d)"
run_bats_file() {
  local bats_file="$1"
  local base out rc args
  base="$(basename "$bats_file")"
  out="${BATS_TMP_DIR}/${base}.tap"
  printf "\n===== %s (running) =====\n" "$base"
  args=(--tap --print-output-on-failure --timing)
  [ -n "${BATS_FILTER:-}" ] && args+=(-f "${BATS_FILTER}")
  [ -n "${BATS_FILTER_STATUS:-}" ] && args+=(--filter-status "${BATS_FILTER_STATUS}")
  bats "${args[@]}" "$bats_file" >"$out" 2>&1
  rc=$?
  printf "\n===== %s =====\n" "$base"
  cat "$out"
  return "$rc"
}
cleanup_bats_tmp() {
  local trash_dir=""
  if [[ -d "$BATS_TMP_DIR" ]]; then
    trash_dir="${HOME}/.Trash/matchy_bats_tmp_$(date +%Y-%m-%d-%H.%M.%S)_$$"
    mkdir -p "$trash_dir"
    mv "$BATS_TMP_DIR" "${trash_dir}/"
  fi
}
trap cleanup_bats_tmp EXIT

bats_native_args=(--print-output-on-failure --timing)
[ -n "${BATS_FILTER:-}" ] && bats_native_args+=(-f "${BATS_FILTER}")
[ -n "${BATS_FILTER_STATUS:-}" ] && bats_native_args+=(--filter-status "${BATS_FILTER_STATUS}")

bats_status=0
cd "$REPO_ROOT"
if [ "${#BATS_PARALLEL_FILES[@]}" -gt 0 ]; then
  if [ "${BATS_USE_NATIVE_JOBS:-false}" = "true" ] && command -v parallel >/dev/null 2>&1; then
    echo "▶ Running Bats shell tests (bats -j ${BATS_JOBS_RESOLVED}, parallel files=${#BATS_PARALLEL_FILES[@]}, GNU parallel)..."
    bats -j "$BATS_JOBS_RESOLVED" --no-parallelize-within-files \
      "${bats_native_args[@]}" "${BATS_PARALLEL_FILES[@]}" || bats_status=$?
  else
    if [ "${BATS_USE_NATIVE_JOBS:-false}" = "true" ]; then
      echo "▶ BATS_USE_NATIVE_JOBS=true but GNU parallel not on PATH; falling back to xargs -P."
    fi
    echo "▶ Running Bats shell tests (parallel by file, jobs=${BATS_JOBS_RESOLVED}, files=${#BATS_PARALLEL_FILES[@]})..."
    # shellcheck disable=SC2016
    printf '%s\0' "${BATS_PARALLEL_FILES[@]}" \
      | BATS_TMP_DIR="$BATS_TMP_DIR" BATS_FILTER="${BATS_FILTER:-}" \
        BATS_FILTER_STATUS="${BATS_FILTER_STATUS:-}" REPO_ROOT="$REPO_ROOT" \
        xargs -0 -P "$BATS_JOBS_RESOLVED" -I {} bash -c '
          f="$1"
          base="$(basename "$f")"
          out="${BATS_TMP_DIR}/${base}.tap"
          printf "\n===== %s (running) =====\n" "$base"
          args=(--tap --print-output-on-failure --timing)
          [ -n "${BATS_FILTER}" ] && args+=(-f "${BATS_FILTER}")
          [ -n "${BATS_FILTER_STATUS}" ] && args+=(--filter-status "${BATS_FILTER_STATUS}")
          cd "${REPO_ROOT}"
          bats "${args[@]}" "$f" >"$out" 2>&1
          rc=$?
          printf "\n===== %s =====\n" "$base"
          cat "$out"
          exit $rc
        ' _ {} \
      || bats_status=$?
  fi
fi
if [ "${#BATS_SERIAL_FILES[@]}" -gt 0 ]; then
  echo "▶ Running Bats shell tests (serial heavy lanes, files=${#BATS_SERIAL_FILES[@]})..."
  for serial_bats_file in "${BATS_SERIAL_FILES[@]}"; do
    run_bats_file "$serial_bats_file" || bats_status=$?
  done
fi
#R025: Fail clearly when parallel Bats execution fails.
if [ "$bats_status" -ne 0 ]; then
  echo "Shell unit tests failed."
  exit 1
fi

#R030: Emit single pass line on successful completion.
echo "✅ PASS: Python and shell unit tests completed."
