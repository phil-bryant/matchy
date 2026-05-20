#!/usr/bin/env bats
# Numbered traceability tags: #R055-T01 #R055-T02 #R055-T03

load "helpers/common.bash"
load "helpers/security_stubs.bash"

setup_file() {
  setup_file_shared_fixture "06_run_security_checks.sh"
}

setup() {
  setup_security_test
}

teardown() {
  teardown_shell_test
}

@test "prints ruff findings to the console" {
  #R055-T02
  stub_security_tools_pass
  make_ruff_stub '[{"filename":"matchy/repository.py","location":{"row":4,"column":25},"code":"F401","message":"unused import","severity":"error"}]'
  run_security_script "ruff,bandit" SECURITY_FAIL_ON_FINDINGS=false
  [ "$status" -eq 0 ]
  [[ "$output" == *"Ruff findings"* ]]
  [[ "$output" == *"matchy/repository.py:4:25 F401 unused import"* ]]
  ruff_finding_line="$(printf '%s\n' "${output}" | awk '/^- \[error\] matchy\/repository.py:4:25 F401 unused import$/{print NR; exit}')"
  bandit_header_line="$(printf '%s\n' "${output}" | awk '/Security Tool: Bandit/{print NR; exit}')"
  [ -n "${ruff_finding_line}" ]
  [ -n "${bandit_header_line}" ]
  [ "${ruff_finding_line}" -lt "${bandit_header_line}" ]
}

@test "prints bandit findings to the console" {
  #R055-T03
  stub_security_tools_pass
  make_bandit_stub '{"results":[{"filename":"./08_run_matchy_api.py","line_number":25,"test_id":"B310","test_name":"blacklist","issue_severity":"MEDIUM","issue_text":"Audit url open"}]}'
  make_pip_audit_stub '{"dependencies":[]}'
  run_security_script "bandit,pip-audit" SECURITY_FAIL_ON_FINDINGS=false
  [ "$status" -eq 0 ]
  [[ "$output" == *"Bandit findings"* ]]
  bandit_finding_line="$(printf '%s\n' "${output}" | awk '/^- \[MEDIUM\] \.\/08_run_matchy_api.py:25 B310/{print NR; exit}')"
  pip_audit_header_line="$(printf '%s\n' "${output}" | awk '/Security Tool: pip-audit/{print NR; exit}')"
  [ -n "${bandit_finding_line}" ]
  [ -n "${pip_audit_header_line}" ]
  [ "${bandit_finding_line}" -lt "${pip_audit_header_line}" ]
}
