#!/usr/bin/env bats

load "helpers/common.bash"

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "05_run_security_checks.sh"
}

teardown() {
  teardown_shell_test
}

@test "fails when shellcheck is missing" {
  #R001: Script runs strict mode from repo root.
  #R005: Report directory is deterministic/configurable.
  #R010: Missing tool handling is explicit.
  #R015: ShellCheck report generation behavior.
  #R020: Semgrep report generation behavior.
  #R025: Gitleaks report generation behavior.
  #R030: Completion line contains report directory.
  run env PATH="/usr/bin:/bin" bash "${FIXTURE_ROOT}/05_run_security_checks.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Missing required command: shellcheck"* ]]
}

@test "writes report files when tools are available" {
  stub_cmd shellcheck "printf '[]'; exit 0"
  stub_cmd semgrep "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd gitleaks "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--report-path\" ]; then printf '[]' > \"\$2\"; fi; shift; done; exit 0"
  run bash "${FIXTURE_ROOT}/05_run_security_checks.sh"
  [ "$status" -eq 0 ]
  [ -f "${FIXTURE_ROOT}/.security-reports/shellcheck.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/semgrep.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/gitleaks.json" ]
}
