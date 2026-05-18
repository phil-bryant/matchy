#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

@test "api health endpoint returns status ok" {
  #R001: Health endpoint returns deterministic status payload.
  #R001-T01: Verify /health response shape and status.
  run env PYTHONPATH="$(pwd)" TELLER_DB_PASSWORD="pw" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from fastapi.testclient import TestClient
from matchy.api import create_app
response = TestClient(create_app()).get("/health")
print(response.status_code == 200 and response.json().get("status") == "ok")
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "api run endpoint maps unknown transaction to http 404" {
  #R005: ValueError from service is converted into HTTP 404.
  #R005-T01: Verify /v1/matchy/runs returns 404 for unknown transaction.
  run env PYTHONPATH="$(pwd)" TELLER_DB_PASSWORD="pw" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from fastapi.testclient import TestClient
import matchy.api as api

class StubService:
    def match_transaction(self, transaction_id, trigger_source="manual"):
        raise ValueError("Unknown transaction_id: missing")

old = api.MatchService
api.MatchService = lambda settings: StubService()
try:
    response = TestClient(api.create_app()).post("/v1/matchy/runs", json={"transaction_ids": ["missing"], "trigger_source": "manual"})
    print(response.status_code == 404)
finally:
    api.MatchService = old
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
