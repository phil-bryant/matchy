#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

load "helpers/common.bash"

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "08_run_matchy_api.py"
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
  teardown_shell_test
}

@test "run script loads app and uses deterministic bind settings" {
  #R001: Script is an executable Python entrypoint.
  #R005: uvicorn bind host/port are deterministic for local runs.
  run env MATCHY_PORT_GUARD="false" PYTHONPATH="${FIXTURE_ROOT}" python3 "${FIXTURE_ROOT}/08_run_matchy_api.py"
  [ "$status" -eq 0 ]
  [[ "$output" == *"host=127.0.0.1"* ]]
  [[ "$output" == *"port=8790"* ]]
}
