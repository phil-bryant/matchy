#!/usr/bin/env bats

load "helpers/common.bash"

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "06_run_av_checks.sh"
}

teardown() {
  teardown_shell_test
}

make_clamscan_stub_clean() {
  cat > "${STUB_BIN}/clamscan" <<'EOF'
#!/usr/bin/env bash
echo "Scanned files: 7"
echo "Infected files: 0"
exit 0
EOF
  chmod +x "${STUB_BIN}/clamscan"
}

make_clamscan_stub_infected() {
  cat > "${STUB_BIN}/clamscan" <<'EOF'
#!/usr/bin/env bash
echo "/tmp/eicar.txt: Win.Test.EICAR_HDB-1 FOUND"
echo "Scanned files: 5"
echo "Infected files: 1"
exit 1
EOF
  chmod +x "${STUB_BIN}/clamscan"
}

make_clamscan_stub_exit_2() {
  cat > "${STUB_BIN}/clamscan" <<'EOF'
#!/usr/bin/env bash
echo "ERROR: scanner failed"
echo "Scanned files: 0"
echo "Infected files: 0"
exit 2
EOF
  chmod +x "${STUB_BIN}/clamscan"
}

make_clamscan_stub_slow_clean() {
  cat > "${STUB_BIN}/clamscan" <<'EOF'
#!/usr/bin/env bash
sleep 2
echo "Scanned files: 11"
echo "Infected files: 0"
exit 0
EOF
  chmod +x "${STUB_BIN}/clamscan"
}

make_clamscan_stub_missing_db_then_clean() {
  cat > "${STUB_BIN}/clamscan" <<'EOF'
#!/usr/bin/env bash
state_file="${CLAMSCAN_STATE_FILE:?}"
if [ ! -f "$state_file" ]; then
  echo "No supported database files found in /var/lib/clamav"
  echo "Scanned files: 0"
  echo "Infected files: 0"
  touch "$state_file"
  exit 2
fi
echo "Scanned files: 9"
echo "Infected files: 0"
exit 0
EOF
  chmod +x "${STUB_BIN}/clamscan"
}

make_freshclam_stub_ok() {
  cat > "${STUB_BIN}/freshclam" <<'EOF'
#!/usr/bin/env bash
echo "freshclam $*" >> "${CALLS_LOG}"
echo "daily database available for download"
exit 0
EOF
  chmod +x "${STUB_BIN}/freshclam"
}

@test "fails when clamscan is missing" {
  #R001: Script runs strict mode from repository root.
  #R005: Missing required command shows actionable guidance.
  #R010: Supports explicit skip mode with deterministic artifacts.
  #R015: Persists raw scanner output and summary artifacts.
  #R020: Reports signature freshness before scanning.
  #R025: Emits heartbeat output for long scans.
  #R030: Persists summary and enforces optional gate behavior.
  #R035: Missing scan target fails clearly.
  #R040: Missing database triggers one-time freshclam retry path.
  #R045: Clamscan execution failures are hard failures.
  #R050: Final completion output includes report directory.
  run env PATH="/usr/bin:/bin" bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Missing required command: clamscan"* ]]
}

@test "runs from non-repo cwd and writes reports under script root" {
  make_clamscan_stub_clean
  mkdir -p "${TEST_TMPDIR}/elsewhere"
  run env RUN_CLAMAV=true PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash -c "cd '${TEST_TMPDIR}/elsewhere' && bash '${FIXTURE_ROOT}/06_run_av_checks.sh'"
  [ "$status" -eq 0 ]
  [ -f "${FIXTURE_ROOT}/.security-reports/clamav.log" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/clamav-summary.json" ]
}

@test "skips ClamAV lane when RUN_CLAMAV=false with deterministic artifacts" {
  #R010
  run env RUN_CLAMAV=false PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 0 ]
  [ -f "${FIXTURE_ROOT}/.security-reports/clamav.log" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/clamav-summary.json" ]
}

@test "writes scanner artifacts and summary with clean scan output" {
  #R015 #R030
  make_clamscan_stub_clean
  run env PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 0 ]
  [ -f "${FIXTURE_ROOT}/.security-reports/clamav.log" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/clamav-summary.json" ]
}

@test "prints signature freshness line before scan execution" {
  #R020
  make_clamscan_stub_clean
  run env PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ClamAV signature freshness:"* ]]
}

@test "prints signature freshness output with custom db" {
  make_clamscan_stub_clean
  local db_dir="${TEST_TMPDIR}/clamdb"
  mkdir -p "$db_dir"
  touch "${db_dir}/main.cvd"
  run env CLAMAV_DB_DIR="$db_dir" CLAMAV_SIGNATURE_MAX_AGE_HOURS=1 PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ClamAV signature freshness:"* ]]
}

@test "prints heartbeat progress while waiting for a slow scan" {
  #R025
  make_clamscan_stub_slow_clean
  run env CLAMAV_HEARTBEAT_SECONDS=1 CLAMAV_POLL_SECONDS=1 PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ClamAV scan in progress"* ]]
}

@test "fails gate when infected files are detected with fail-on-high enabled" {
  #R030
  make_clamscan_stub_infected
  run env SECURITY_FAIL_ON_HIGH_CRITICAL=true PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"ClamAV detected infected files"* ]]
  [[ "$output" == *"Antivirus (ClamAV) gate failed"* ]]
}

@test "fails clearly when configured scan target does not exist" {
  #R035
  make_clamscan_stub_clean
  run env CLAMAV_SCAN_TARGET="./does-not-exist" PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"ClamAV scan target not found"* ]]
}

@test "refreshes signatures once and retries when database files are missing" {
  #R040
  make_clamscan_stub_missing_db_then_clean
  make_freshclam_stub_ok
  export CLAMSCAN_STATE_FILE="${TEST_TMPDIR}/clamscan.state"
  run env CLAMSCAN_STATE_FILE="${CLAMSCAN_STATE_FILE}" PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"attempting one-time database refresh with freshclam --stdout"* ]]
  [[ "$output" == *"Retrying ClamAV repository scan"* ]]
}

@test "fails on execution error when clamscan exits greater than one" {
  #R045
  make_clamscan_stub_exit_2
  run env PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"ClamAV failed to execute."* ]]
}

@test "prints deterministic final completion output with report path" {
  #R050
  make_clamscan_stub_clean
  run env PATH="${STUB_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    bash "${FIXTURE_ROOT}/06_run_av_checks.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"AV checks completed. Reports:"* ]]
}
