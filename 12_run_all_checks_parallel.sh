#!/usr/bin/env bash
#R001: Run in strict shell mode and fail fast.
umask 007
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#R005: Execute from repository root regardless of caller directory.
cd "$SCRIPT_DIR"

#R010: Fixed checklist of seven numbered check scripts.
CHECKS=(
  "00_verify_requirements_traceability.sh"
  "04_run_dependency_freshness_checks.sh"
  "05_run_unit_tests.sh"
  "06_run_security_checks.sh"
  "07_run_av_checks.sh"
  "10_run_mutation_tests.sh"
  "11_run_fuzz.sh"
)

#R040: Remain a standalone meta-runner; child check scripts must not invoke this script.

#R035: Persist per-check stdout/stderr log artifacts.
REPORT_DIR="${PARALLEL_CHECKS_REPORT_DIR:-./.parallel-checks-reports}"
mkdir -p "$REPORT_DIR"
PROGRESS_INTERVAL_SECONDS="${PARALLEL_CHECKS_PROGRESS_INTERVAL_SECONDS:-1}"
if [[ ! "$PROGRESS_INTERVAL_SECONDS" =~ ^[0-9]+$ || "$PROGRESS_INTERVAL_SECONDS" -le 0 ]]; then
  PROGRESS_INTERVAL_SECONDS=1
fi
LOCK_FILE="${SCRIPT_DIR}/.12_run_all_checks_parallel.lock"
PROGRESS_INLINE=false
if [[ -t 1 ]]; then
  PROGRESS_INLINE=true
fi
child_pids=()
cleanup_finished=false
signal_exit_code=""

safe_move_to_trash() {
  local path="$1"
  local trash_dir=""
  [[ -e "$path" ]] || return 0
  trash_dir="${HOME}/.Trash/matchy_parallel_$(date +%Y-%m-%d-%H.%M.%S)_$$"
  mkdir -p "$trash_dir"
  mv "$path" "${trash_dir}/$(basename "$path")"
}

#R050: Prevent concurrent invocations of this orchestrator from the same repo root.
release_single_run_lock() {
  local current_lock_pid=""
  if [[ -f "$LOCK_FILE" ]]; then
    current_lock_pid="$(<"$LOCK_FILE")"
    if [[ "$current_lock_pid" == "$$" ]]; then
      safe_move_to_trash "$LOCK_FILE"
    fi
  fi
}

acquire_single_run_lock() {
  local existing_lock_pid=""
  if ( set -o noclobber; echo "$$" > "$LOCK_FILE" ) 2>/dev/null; then
    return 0
  fi
  if [[ -f "$LOCK_FILE" ]]; then
    existing_lock_pid="$(<"$LOCK_FILE")"
  fi
  if [[ -n "$existing_lock_pid" ]] && kill -0 "$existing_lock_pid" 2>/dev/null; then
    echo "❌ FAIL: another 12_run_all_checks_parallel.sh run is already active (pid ${existing_lock_pid})." >&2
    return 1
  fi
  safe_move_to_trash "$LOCK_FILE"
  if ( set -o noclobber; echo "$$" > "$LOCK_FILE" ) 2>/dev/null; then
    return 0
  fi
  echo "❌ FAIL: unable to acquire single-run lock at ${LOCK_FILE}" >&2
  return 1
}

#R055: Terminate launched child checks on interrupt or termination.
run_in_new_session() {
  if command -v setsid >/dev/null 2>&1; then
    setsid "$@"
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import os, sys
os.setsid()
os.execvp(sys.argv[1], sys.argv[1:])' "$@"
  else
    "$@"
  fi
}

kill_process_tree() {
  local signal="$1"
  local root_pid="$2"
  local child

  [[ -n "$root_pid" && "$root_pid" -ne $$ ]] || return 0
  for child in $(pgrep -P "$root_pid" 2>/dev/null || true); do
    kill_process_tree "$signal" "$child"
  done
  kill -"$signal" "$root_pid" 2>/dev/null || true
}

# shellcheck disable=SC2329
terminate_child_checks() {
  local pid script match_pid

  for pid in "${child_pids[@]}"; do
    [[ -n "$pid" ]] || continue
    kill_process_tree TERM "$pid"
    kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  done

  for script in "${CHECKS[@]}"; do
    while IFS= read -r match_pid; do
      kill_process_tree TERM "$match_pid"
    done < <(pgrep -f "${SCRIPT_DIR}/${script}" 2>/dev/null || true)
  done

  sleep 1

  for pid in "${child_pids[@]}"; do
    [[ -n "$pid" ]] || continue
    kill_process_tree KILL "$pid"
    kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  done

  for script in "${CHECKS[@]}"; do
    while IFS= read -r match_pid; do
      kill_process_tree KILL "$match_pid"
    done < <(pgrep -f "${SCRIPT_DIR}/${script}" 2>/dev/null || true)
  done
}

# shellcheck disable=SC2329
finish_run_cleanup() {
  if [[ "$cleanup_finished" == "true" ]]; then
    return 0
  fi
  cleanup_finished=true
  finish_progress_line
  release_single_run_lock
}

# shellcheck disable=SC2329
stop_on_signal() {
  local exit_code="$1"
  if [[ "$cleanup_finished" == "true" ]]; then
    exit "$exit_code"
  fi
  cleanup_finished=true
  terminate_child_checks
  finish_progress_line
  echo "Interrupted; stopped parallel checks." >&2
  release_single_run_lock
  exit "$exit_code"
}

check_for_signal() {
  if [[ -n "$signal_exit_code" ]]; then
    stop_on_signal "$signal_exit_code"
  fi
}

# shellcheck disable=SC2329
record_sigint() {
  signal_exit_code=130
}

# shellcheck disable=SC2329
record_sigterm() {
  signal_exit_code=143
}

trap finish_run_cleanup EXIT
trap record_sigint INT
trap record_sigterm TERM
acquire_single_run_lock

render_progress() {
  local completed="$1"
  local total="$2"
  local bar_width=20
  local percent=0
  local filled=0
  local empty=0
  local filled_bar=""
  local empty_bar=""

  if [[ "$total" -gt 0 ]]; then
    percent=$((completed * 100 / total))
    filled=$((completed * bar_width / total))
  fi
  empty=$((bar_width - filled))
  filled_bar="$(printf '%*s' "$filled" '' | tr ' ' '#')"
  empty_bar="$(printf '%*s' "$empty" '' | tr ' ' '-')"
  if [[ "$PROGRESS_INLINE" == "true" ]]; then
    printf '\r\033[2KProgress: [%s/%s (%s%%)] [%s%s]' "$completed" "$total" "$percent" "$filled_bar" "$empty_bar"
  else
    echo "Progress: [${completed}/${total} (${percent}%)] [${filled_bar}${empty_bar}]"
  fi
}

emit_result_line() {
  local message="$1"
  if [[ "$PROGRESS_INLINE" == "true" ]]; then
    printf '\r\033[2K'
  fi
  echo "$message"
}

finish_progress_line() {
  if [[ "$PROGRESS_INLINE" == "true" ]]; then
    printf '\n'
  fi
}

for script in "${CHECKS[@]}"; do
  if [[ ! -f "./${script}" ]]; then
    echo "❌ FAIL: expected check script not found: ./${script}" >&2
    exit 1
  fi
done

echo "▶ Starting parallel checks (${#CHECKS[@]} scripts)..."

COMPLETION_FIFO="${REPORT_DIR}/.completion.fifo"
safe_move_to_trash "$COMPLETION_FIFO"
mkfifo "$COMPLETION_FIFO"
exec 3<> "$COMPLETION_FIFO"

#R046: Export lane count so nested parallel runners divide inner concurrency.
export PARALLEL_LANES="${#CHECKS[@]}"

#R060: Record orchestrator wall-clock start for long-pole timing.
run_start_epoch="$(date +%s)"
long_pole_script=""
long_pole_seconds=0

#R015: Launch all check scripts concurrently in isolated sessions.
#R020: Capture each child exit code independently.
for script in "${CHECKS[@]}"; do
  log="${REPORT_DIR}/${script%.sh}.log"
  safe_move_to_trash "${log}"
  safe_move_to_trash "${log}.exit"
  safe_move_to_trash "${log}.start"
  date +%s > "${log}.start"
  # shellcheck disable=SC2016
  run_in_new_session env \
    CHECK_ROOT="${SCRIPT_DIR}" \
    CHECK_NAME="${script}" \
    CHECK_LOG="${log}" \
    bash -c 'set +e
cd "${CHECK_ROOT}"
./"${CHECK_NAME}" >"${CHECK_LOG}" 2>&1
exit_code=$?
echo "${exit_code}" > "${CHECK_LOG}.exit"
printf "%s|%s\n" "${CHECK_NAME}" "${exit_code}" >&3' &
  child_pids+=("$!")
done

if [[ "${PARALLEL_CHECKS_TEST_INTERRUPT:-}" == "1" ]]; then
  if [[ -n "${PARALLEL_CHECKS_TEST_INTERRUPT_WAIT:-}" ]]; then
    interrupt_wait_deadline=$(( $(date +%s) + 5 ))
    while [[ ! -f "${PARALLEL_CHECKS_TEST_INTERRUPT_WAIT}" ]]; do
      if [[ $(date +%s) -ge "$interrupt_wait_deadline" ]]; then
        break
      fi
      sleep 0.05
    done
  fi
  stop_on_signal 130
fi

#R025: Print each pass/fail line as soon as its check completes (completion order).
pass_count=0
fail_count=0
total="${#CHECKS[@]}"
reported=0
reported_scripts=()

record_check_result() {
  local completed_script="$1"
  local completed_exit="$2"
  local already_reported=false
  local seen_script=""

  for seen_script in ${reported_scripts[@]+"${reported_scripts[@]}"}; do
    if [[ "$seen_script" == "$completed_script" ]]; then
      already_reported=true
    fi
  done
  if [[ "$already_reported" == "true" ]]; then
    return 0
  fi
  reported_scripts+=("$completed_script")
  reported=$((reported + 1))
  log="${REPORT_DIR}/${completed_script%.sh}.log"
  start_epoch="$(<"${log}.start")"
  elapsed=$(( $(date +%s) - start_epoch ))
  if [[ "$elapsed" -gt "$long_pole_seconds" ]]; then
    long_pole_seconds=$elapsed
    long_pole_script="$completed_script"
  fi
  if [[ "$completed_exit" -eq 0 ]]; then
    emit_result_line "✅ PASS: ${completed_script} (${elapsed}s)"
    pass_count=$((pass_count + 1))
  else
    emit_result_line "❌ FAIL: ${completed_script} (exit ${completed_exit}, ${elapsed}s) — see ${log}"
    fail_count=$((fail_count + 1))
  fi
}

recover_missing_completions() {
  local script=""

  for script in "${CHECKS[@]}"; do
    log="${REPORT_DIR}/${script%.sh}.log"
    if [[ -f "${log}.exit" ]]; then
      record_check_result "$script" "$(<"${log}.exit")"
    fi
  done
}

all_checks_have_exit_files() {
  local script=""

  for script in "${CHECKS[@]}"; do
    log="${REPORT_DIR}/${script%.sh}.log"
    if [[ ! -f "${log}.exit" ]]; then
      return 1
    fi
  done
  return 0
}

#R045: Emit continuous aggregate progress while checks are still running.
render_progress "$reported" "$total"
while [[ "$reported" -lt "$total" ]]; do
  check_for_signal
  if IFS='|' read -r -t "$PROGRESS_INTERVAL_SECONDS" completed_script completed_exit <&3; then
    record_check_result "$completed_script" "$completed_exit"
  elif all_checks_have_exit_files; then
    recover_missing_completions
  fi
  check_for_signal
  render_progress "$reported" "$total"
done
exec 3>&-

set +e
for pid in "${child_pids[@]}"; do
  wait "$pid"
done
set -e

#R060: Report wall time and longest lane before overall gate.
wall_elapsed=$(( $(date +%s) - run_start_epoch ))
echo "Timing: wall ${wall_elapsed}s; long pole ${long_pole_script} (${long_pole_seconds}s)"

#R030: Print overall pass/fail gate and exit code.
if [[ "$fail_count" -eq 0 ]]; then
  echo "✅ PASS: all parallel checks succeeded (${pass_count}/${total})"
  exit 0
fi

echo "❌ FAIL: parallel checks: ${pass_count}/${total} passed"
exit 1
