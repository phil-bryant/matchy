#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R010-T02 #R010-T03

load "helpers/common.bash"

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "09_run_matchy_driver.py"
  cat > "${FIXTURE_ROOT}/requests.py" <<'EOF'
import json as json_mod
import os
import time

_CALLS_FILE = os.environ.get("MATCHY_TEST_CALLS_FILE", "")

class HTTPError(Exception):
    def __init__(self, response=None):
        self.response = response

class RequestException(Exception):
    pass

class _Response:
    def __init__(self, body):
        self._body = body
        self.status_code = 200
    def raise_for_status(self):
        pass
    def json(self):
        return json_mod.loads(self._body)

def post(url, json=None, timeout=0):
    sleep_seconds = float(os.environ.get("MATCHY_TEST_POST_SLEEP_SECONDS", "0").strip() or "0")
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    payload = json or {}
    record = {"url": url, "method": "POST", "timeout": timeout, "payload": payload}
    if _CALLS_FILE:
        with open(_CALLS_FILE, "a", encoding="utf-8") as handle:
            handle.write(json_mod.dumps(record) + "\n")
    return _Response(json_mod.dumps({"results": [{"selected_message_ids": ["m1", "m2"]}]}))
EOF
}

teardown() {
  teardown_shell_test
}

@test "driver one-shot mode posts pending match request with configured payload" {
  #R001: Script has executable entrypoint and one-shot driver behavior.
  #R001-T01: MATCHY_DRIVER_ONCE=true performs a single pending endpoint request.
  #R005: Driver posts deterministic payload fields with env-var overrides.
  #R005-T01: Posted URL, payload, and timeout reflect configured values.
  export MATCHY_TEST_CALLS_FILE="${TEST_TMPDIR}/calls.jsonl"
  run env PYTHONPATH="${FIXTURE_ROOT}" MATCHY_DRIVER_ONCE="true" MATCHY_API_BASE_URL="http://127.0.0.1:8790" MATCHY_DRIVER_LIMIT="9" MATCHY_DRIVER_LOOKBACK_DAYS="3" MATCHY_DRIVER_TRIGGER_SOURCE="auto" MATCHY_DRIVER_TIMEOUT_SECONDS="7" python3 "${FIXTURE_ROOT}/09_run_matchy_driver.py"
  [ "$status" -eq 0 ]
  [[ "$output" == *"driver_run=1 status=ok"* ]]
  [[ "$output" == *"batch_size=1 selected_messages=2"* ]]
  #R010: Profiling logs are off unless --profile is passed.
  [[ "$output" != *"[matchy-driver-startup +"* ]]
  [ -f "${MATCHY_TEST_CALLS_FILE}" ]
  local calls_text
  calls_text="$(cat "${MATCHY_TEST_CALLS_FILE}")"
  [[ "$calls_text" == *"\"url\": \"http://127.0.0.1:8790/v1/matchy/runs/pending\""* ]]
  [[ "$calls_text" == *"\"method\": \"POST\""* ]]
  [[ "$calls_text" == *"\"timeout\": 7"* ]]
  [[ "$calls_text" == *"\"limit\": 9"* ]]
  [[ "$calls_text" == *"\"lookback_days\": 3"* ]]
  [[ "$calls_text" == *"\"trigger_source\": \"auto\""* ]]
}

@test "driver --profile emits startup timing logs" {
  #R010: --profile enables startup timing logs for driver initialization phases.
  run env PYTHONPATH="${FIXTURE_ROOT}" MATCHY_DRIVER_ONCE="true" python3 "${FIXTURE_ROOT}/09_run_matchy_driver.py" --profile
  [ "$status" -eq 0 ]
  [[ "$output" == *"[matchy-driver-startup +"* ]]
  [[ "$output" == *"driver_run=1 status=ok"* ]]
}

@test "driver --profile emits waiting heartbeat while request is in flight" {
  #R010: --profile surfaces in-flight wait heartbeats during long pending-run HTTP calls.
  run env PYTHONPATH="${FIXTURE_ROOT}" MATCHY_DRIVER_ONCE="true" MATCHY_TEST_POST_SLEEP_SECONDS="6" python3 "${FIXTURE_ROOT}/09_run_matchy_driver.py" --profile
  [ "$status" -eq 0 ]
  [[ "$output" == *"run-waiting"* ]]
  [[ "$output" == *"driver_run=1 status=ok"* ]]
}
