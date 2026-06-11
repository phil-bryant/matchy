#!/usr/bin/env bats

load "helpers/common.bash"

setup() {
  #R001: Test fixture setup supports executable entrypoint validation.
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "06_run_matchy_api.py"
  mkdir -p "${FIXTURE_ROOT}/matchy"
  cat > "${FIXTURE_ROOT}/matchy/api.py" <<'EOF'
def create_app():
    return {"ok": True}
EOF
  cat > "${FIXTURE_ROOT}/uvicorn.py" <<'EOF'
def run(app, host, port):
    print(f"uvicorn-run host={host} port={port} app={app}")
EOF
}

teardown() {
  #R001: Test fixture teardown keeps script lane deterministic.
  teardown_shell_test
}

@test "run script loads app and uses deterministic bind settings" {
  #R001: Script is an executable Python entrypoint.
  #R001-T01: Script executes in fixture and reaches uvicorn launch path.
  #R005: uvicorn bind host/port are deterministic for local runs.
  #R005-T01: Host/port match deterministic default bind settings.
  run env MATCHY_PORT_GUARD="false" PYTHONPATH="${FIXTURE_ROOT}" python3 "${FIXTURE_ROOT}/06_run_matchy_api.py"
  [ "$status" -eq 0 ]
  [[ "$output" == *"host=127.0.0.1"* ]]
  [[ "$output" == *"port=8790"* ]]
  #R010: Profiling is opt-in and must stay quiet by default.
  #R010-T01: Startup profiling lines are absent unless --profile is supplied.
  [[ "$output" != *"[matchy-startup +"* ]]
}

@test "run script emits startup profiling logs only with --profile" {
  #R010: --profile enables startup timing logs for launcher startup phases.
  #R010-T02: Startup profiling lines are emitted when --profile is supplied.
  run env MATCHY_PORT_GUARD="false" PYTHONPATH="${FIXTURE_ROOT}" python3 "${FIXTURE_ROOT}/06_run_matchy_api.py" --profile
  [ "$status" -eq 0 ]
  [[ "$output" == *"[matchy-startup +"* ]]
}
