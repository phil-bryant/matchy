#!/usr/bin/env bats

load "helpers/common.bash"

teardown() {
  teardown_shell_test
}

src() {
  printf '%s' "$(repo_root)/04_run_all_tests_parallel.sh"
}

@test "enables secure umask and strict shell mode" {
  #R001-T01
  run grep "umask 007" "$(src)"
  [ "$status" -eq 0 ]
  run grep "set -euo pipefail" "$(src)"
  [ "$status" -eq 0 ]
}

@test "derives script and runner paths from script location" {
  #R005-T01
  run grep "SCRIPT_DIR=" "$(src)"
  [ "$status" -eq 0 ]
  run grep "RUNNER_HOME=" "$(src)"
  [ "$status" -eq 0 ]
  run grep "runner" "$(src)"
  [ "$status" -eq 0 ]
}

@test "loads matchy runbook profile before delegation" {
  #R010-T01
  run grep "export RUNBOOK_REPO_ROOT" "$(src)"
  [ "$status" -eq 0 ]
  run grep "config/runbook/matchy.env" "$(src)"
  [ "$status" -eq 0 ]
}

@test "delegates to mapped runner orchestrator golden" {
  #R015-T01
  run grep "exec \"\${RUNNER_HOME}/07_run_all_tests_parallel.sh\" \"\$@\"" "$(src)"
  [ "$status" -eq 0 ]
}
