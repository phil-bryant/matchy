#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

load "helpers/common.bash"

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "09_run_matchy_driver.py"
  mkdir -p "${FIXTURE_ROOT}/urllib"
  cat > "${FIXTURE_ROOT}/urllib/__init__.py" <<'EOF'
# fixture urllib package marker
EOF
  cat > "${FIXTURE_ROOT}/urllib/error.py" <<'EOF'
class HTTPError(Exception):
    def __init__(self, code=500):
        self.code = code

class URLError(Exception):
    def __init__(self, reason="network"):
        self.reason = reason
EOF
  cat > "${FIXTURE_ROOT}/urllib/request.py" <<'EOF'
import json
import os

_CALLS_FILE = os.environ.get("MATCHY_TEST_CALLS_FILE", "")

class Request:
    def __init__(self, url, data=None, headers=None, method="GET"):
        self.full_url = url
        self.data = data
        self.headers = headers or {}
        self.method = method

class _Response:
    def __init__(self, body):
        self._body = body
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def read(self):
        return self._body.encode("utf-8")

def urlopen(request, timeout=0):
    record = {
        "url": request.full_url,
        "method": request.method,
        "timeout": timeout,
        "payload": json.loads((request.data or b"{}").decode("utf-8")),
    }
    if _CALLS_FILE:
        with open(_CALLS_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    return _Response(json.dumps({"results": [{"selected_message_ids": ["m1", "m2"]}]}))
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
