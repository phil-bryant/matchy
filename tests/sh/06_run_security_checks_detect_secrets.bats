#!/usr/bin/env bats
# Numbered traceability tags: #R060-T01 #R060-T02

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

@test "long-running detect-secrets prints heartbeat before the next tool header" {
  #R060-T01
  make_detect_secrets_stub '{"results":{}}' 'sleep 2;'
  make_ruff_stub '[]'
  run_security_script "detect-secrets,ruff" \
    DETECT_SECRETS_USE_BACKGROUND_WAIT=true \
    DETECT_SECRETS_HEARTBEAT_SECONDS=1 \
    SECURITY_FAIL_ON_FINDINGS=false
  [ "$status" -eq 0 ]
  [[ "$output" == *"… detect-secrets still running (1s elapsed)"* ]]
  heartbeat_line="$(printf '%s\n' "${output}" | awk '/^… detect-secrets still running \(1s elapsed\)$/{print NR; exit}')"
  ruff_header_line="$(printf '%s\n' "${output}" | awk '/Security Tool: Ruff/{print NR; exit}')"
  [ -n "${heartbeat_line}" ]
  [ -n "${ruff_header_line}" ]
  [ "${heartbeat_line}" -lt "${ruff_header_line}" ]
}

@test "detect-secrets prints findings with source lines before the next tool header" {
  #R060-T02
  make_detect_secrets_stub '{"results":{"06_run_security_checks.sh":[{"type":"Secret Keyword","line_number":1}]}}'
  make_ruff_stub '[]'
  run_security_script "detect-secrets,ruff" SECURITY_FAIL_ON_FINDINGS=false
  [ "$status" -eq 0 ]
  [[ "$output" == *"detect-secrets findings"* ]]
  [[ "$output" == *"  source: #!/usr/bin/env bash"* ]]
  detect_source_line="$(printf '%s\n' "${output}" | awk '/^  source: #!\/usr\/bin\/env bash$/{print NR; exit}')"
  ruff_header_line="$(printf '%s\n' "${output}" | awk '/Security Tool: Ruff/{print NR; exit}')"
  [ -n "${detect_source_line}" ]
  [ -n "${ruff_header_line}" ]
  [ "${detect_source_line}" -lt "${ruff_header_line}" ]
}
