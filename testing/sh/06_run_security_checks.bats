#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R015-T01 #R020-T01 #R025-T01 #R030-T01 #R030-T02 #R035-T01 #R040-T01 #R045-T01 #R045-T02 #R050-T01 #R055-T01 #R055-T02 #R055-T03 #R060-T01 #R060-T02

load "helpers/common.bash"

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "06_run_security_checks.sh"
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
  #R035: Standardized tool header format is emitted per lane.
  #R040: Running indicators are emitted before each lane executes.
  run env PATH="/usr/bin:/bin" bash "${FIXTURE_ROOT}/06_run_security_checks.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Missing required command: shellcheck"* ]]
}

@test "writes report files when tools are available" {
  stub_cmd shellcheck "printf '[]'; exit 0"
  stub_cmd semgrep "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd gitleaks "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--report-path\" ]; then printf '[]' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd detect-secrets "printf '{\"results\":{}}'; exit 0"
  stub_cmd ruff "printf '[]'; exit 0"
  stub_cmd bandit "printf '%s' \"\$*\" > \"${FIXTURE_ROOT}/bandit-args.txt\"; while [ \$# -gt 0 ]; do if [ \"\$1\" = \"-o\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd pip-audit "printf '%s' \"\$*\" > \"${FIXTURE_ROOT}/pip-audit-args.txt\"; while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"dependencies\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  cat > "${FIXTURE_ROOT}/requirements.txt" <<'EOF'
requests>=2.34.0
EOF
  run bash "${FIXTURE_ROOT}/06_run_security_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"+==============================================================================+"* ]]
  [[ "$output" == *"Security Tool: ShellCheck"* ]]
  [[ "$output" == *"▶ Running ShellCheck"* ]]
  [[ "$output" == *"✅ PASS: ShellCheck"* ]]
  [[ "$output" == *"✅ Security checks PASSED. Reports:"* ]]
  [ -f "${FIXTURE_ROOT}/.security-reports/security-summary.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/shellcheck.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/semgrep.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/gitleaks.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/detect-secrets.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/ruff.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/bandit.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/pip-audit.json" ]
  bandit_args="$(<"${FIXTURE_ROOT}/bandit-args.txt")"
  [[ "$bandit_args" != *"./matchy-venv"* ]]
  [[ "$bandit_args" == *"./matchy"* ]]
  pip_audit_args="$(<"${FIXTURE_ROOT}/pip-audit-args.txt")"
  [[ "$pip_audit_args" == *"requirements.txt"* ]]
}

@test "uses isolated pip-audit cache directory to avoid stale-cache warnings" {
  #R045: pip-audit cache isolation is enforced without output suppression.
  stub_cmd shellcheck "printf '[]'; exit 0"
  stub_cmd semgrep "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd gitleaks "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--report-path\" ]; then printf '[]' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd detect-secrets "printf '{\"results\":{}}'; exit 0"
  stub_cmd ruff "printf '[]'; exit 0"
  stub_cmd bandit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"-o\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd pip-audit "printf '%s' \"\$PIP_CACHE_DIR\" > \"${FIXTURE_ROOT}/pip-cache-dir.txt\"; while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"dependencies\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  cat > "${FIXTURE_ROOT}/requirements.txt" <<'EOF'
requests>=2.34.0
EOF
  run bash "${FIXTURE_ROOT}/06_run_security_checks.sh"
  [ "$status" -eq 0 ]
  [ -d "${FIXTURE_ROOT}/.security-reports/.pip-cache" ]
  pip_cache_dir="$(<"${FIXTURE_ROOT}/pip-cache-dir.txt")"
  [ "$pip_cache_dir" = "./.security-reports/.pip-cache" ]
  [[ "$output" == *"▶ Running pip-audit"* ]]
}

@test "fails when a lane reports findings" {
  #R030: Per-lane and overall pass/fail output reflects findings.
  #R050: Overall gate fails when findings are present.
  #R055: ShellCheck findings are printed to the console.
  stub_cmd shellcheck 'printf '"'"'[{"file":"bad.sh","line":1,"code":2086,"message":"issue","level":"warning"}]'"'"'; exit 1'
  stub_cmd semgrep "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd gitleaks "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--report-path\" ]; then printf '[]' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd detect-secrets "printf '{\"results\":{}}'; exit 0"
  stub_cmd ruff "printf '[]'; exit 0"
  stub_cmd bandit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"-o\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd pip-audit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"dependencies\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  run bash "${FIXTURE_ROOT}/06_run_security_checks.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"ShellCheck findings"* ]]
  [[ "$output" == *"bad.sh:1 SC2086 issue"* ]]
  [[ "$output" == *"❌ FAIL: ShellCheck"* ]]
  [[ "$output" == *"✅ PASS: Semgrep"* ]]
  [[ "$output" == *"❌ Security checks FAILED. Reports:"* ]]
}

@test "prints ruff findings to the console" {
  #R055: Ruff findings are printed from JSON before the next tool header.
  stub_cmd shellcheck "printf '[]'; exit 0"
  stub_cmd semgrep "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd gitleaks "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--report-path\" ]; then printf '[]' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd detect-secrets "printf '{\"results\":{}}'; exit 0"
  stub_cmd ruff 'printf '"'"'[{"filename":"matchy/repository.py","location":{"row":4,"column":25},"code":"F401","message":"unused import","severity":"error"}]'"'"'; exit 0'
  stub_cmd bandit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"-o\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd pip-audit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"dependencies\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  run env SECURITY_FAIL_ON_FINDINGS=false bash "${FIXTURE_ROOT}/06_run_security_checks.sh"
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
  #R055: Bandit findings are printed from JSON before the next tool header.
  stub_cmd shellcheck "printf '[]'; exit 0"
  stub_cmd semgrep "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd gitleaks "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--report-path\" ]; then printf '[]' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd detect-secrets "printf '{\"results\":{}}'; exit 0"
  stub_cmd ruff "printf '[]'; exit 0"
  stub_cmd bandit 'while [ $# -gt 0 ]; do if [ "$1" = "-o" ]; then printf '"'"'{"results":[{"filename":"./08_run_matchy_api.py","line_number":25,"test_id":"B310","test_name":"blacklist","issue_severity":"MEDIUM","issue_text":"Audit url open"}]}'"'"' > "$2"; fi; shift; done; exit 0'
  stub_cmd pip-audit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"dependencies\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  run env SECURITY_FAIL_ON_FINDINGS=false bash "${FIXTURE_ROOT}/06_run_security_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Bandit findings"* ]]
  [[ "$output" == *"./08_run_matchy_api.py:25 B310"* ]]
  bandit_finding_line="$(printf '%s\n' "${output}" | awk '/^- \[MEDIUM\] \.\/08_run_matchy_api.py:25 B310/{print NR; exit}')"
  pip_audit_header_line="$(printf '%s\n' "${output}" | awk '/Security Tool: pip-audit/{print NR; exit}')"
  [ -n "${bandit_finding_line}" ]
  [ -n "${pip_audit_header_line}" ]
  [ "${bandit_finding_line}" -lt "${pip_audit_header_line}" ]
}

@test "long-running detect-secrets prints heartbeat before the next tool header" {
  #R060: Heartbeat output appears while detect-secrets is still running.
  stub_cmd shellcheck "printf '[]'; exit 0"
  stub_cmd semgrep "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd gitleaks "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--report-path\" ]; then printf '[]' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd detect-secrets "sleep 16; printf '{\"results\":{}}'; exit 0"
  stub_cmd ruff "printf '[]'; exit 0"
  stub_cmd bandit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"-o\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd pip-audit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"dependencies\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  run env SECURITY_FAIL_ON_FINDINGS=false bash "${FIXTURE_ROOT}/06_run_security_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"… detect-secrets still running (15s elapsed)"* ]]
  heartbeat_line="$(printf '%s\n' "${output}" | awk '/^… detect-secrets still running \(15s elapsed\)$/{print NR; exit}')"
  ruff_header_line="$(printf '%s\n' "${output}" | awk '/Security Tool: Ruff/{print NR; exit}')"
  [ -n "${heartbeat_line}" ]
  [ -n "${ruff_header_line}" ]
  [ "${heartbeat_line}" -lt "${ruff_header_line}" ]
}

@test "detect-secrets prints findings with source lines before the next tool header" {
  #R060: Inline finding output includes source lines for each detect-secrets match.
  stub_cmd shellcheck "printf '[]'; exit 0"
  stub_cmd semgrep "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd gitleaks "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--report-path\" ]; then printf '[]' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd detect-secrets 'printf '"'"'{"results":{"06_run_security_checks.sh":[{"type":"Secret Keyword","line_number":1}]}}'"'"'; exit 0'
  stub_cmd ruff "printf '[]'; exit 0"
  stub_cmd bandit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"-o\" ]; then printf '{\"results\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  stub_cmd pip-audit "while [ \$# -gt 0 ]; do if [ \"\$1\" = \"--output\" ]; then printf '{\"dependencies\":[]}' > \"\$2\"; fi; shift; done; exit 0"
  run env SECURITY_FAIL_ON_FINDINGS=false bash "${FIXTURE_ROOT}/06_run_security_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"detect-secrets findings"* ]]
  [[ "$output" == *"- 06_run_security_checks.sh:1 [Secret Keyword]"* ]]
  [[ "$output" == *"  source: #!/usr/bin/env bash"* ]]
  detect_finding_line="$(printf '%s\n' "${output}" | awk '/^- 06_run_security_checks.sh:1 \[Secret Keyword\]$/{print NR; exit}')"
  detect_source_line="$(printf '%s\n' "${output}" | awk '/^  source: #!\/usr\/bin\/env bash$/{print NR; exit}')"
  ruff_header_line="$(printf '%s\n' "${output}" | awk '/Security Tool: Ruff/{print NR; exit}')"
  [ -n "${detect_finding_line}" ]
  [ -n "${detect_source_line}" ]
  [ -n "${ruff_header_line}" ]
  [ "${detect_source_line}" -eq "$((detect_finding_line + 1))" ]
  [ "${detect_source_line}" -lt "${ruff_header_line}" ]
}
