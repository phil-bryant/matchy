#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01

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

@test "api pending run endpoint delegates to service batch matcher" {
  #R010: Pending-run endpoint delegates to service batch matching with validated request fields.
  #R010-T01: Verify /v1/matchy/runs/pending passes limit/lookback/trigger_source and returns service rows.
  run env PYTHONPATH="$(pwd)" TELLER_DB_PASSWORD="pw" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from fastapi.testclient import TestClient
import matchy.api as api

class StubService:
    def match_pending_transactions(self, limit=100, lookback_days=14, trigger_source="auto"):
        return [{"ok": True, "limit": limit, "lookback_days": lookback_days, "trigger_source": trigger_source}]

old = api.MatchService
api.MatchService = lambda settings: StubService()
try:
    response = TestClient(api.create_app()).post(
        "/v1/matchy/runs/pending",
        json={"limit": 7, "lookback_days": 3, "trigger_source": "auto"},
    )
    body = response.json()
    good = response.status_code == 200 and body["results"][0]["limit"] == 7 and body["results"][0]["lookback_days"] == 3
    print(good and body["results"][0]["trigger_source"] == "auto")
finally:
    api.MatchService = old
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
