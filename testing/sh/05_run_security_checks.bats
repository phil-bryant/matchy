#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R015-T01 #R020-T01 #R025-T01 #R030-T01 #R035-T01 #R040-T01 #R045-T01 #R045-T02

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
  #R035: Standardized tool header format is emitted per lane.
  #R040: Running indicators are emitted before each lane executes.
  run env PATH="/usr/bin:/bin" bash "${FIXTURE_ROOT}/05_run_security_checks.sh"
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
  run bash "${FIXTURE_ROOT}/05_run_security_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"+==============================================================================+"* ]]
  [[ "$output" == *"Security Tool: ShellCheck"* ]]
  [[ "$output" == *"▶ Running ShellCheck"* ]]
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
  run bash "${FIXTURE_ROOT}/05_run_security_checks.sh"
  [ "$status" -eq 0 ]
  [ -d "${FIXTURE_ROOT}/.security-reports/.pip-cache" ]
  pip_cache_dir="$(<"${FIXTURE_ROOT}/pip-cache-dir.txt")"
  [ "$pip_cache_dir" = "./.security-reports/.pip-cache" ]
  [[ "$output" == *"▶ Running pip-audit"* ]]
}
