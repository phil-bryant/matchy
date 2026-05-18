#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

@test "api health endpoint returns status ok" {
  #R001: Health endpoint returns deterministic status payload.
  #R001-T01: Verify /health response shape and status.
  run env PYTHONPATH="$(pwd)" python3 -c "from fastapi.testclient import TestClient; from matchy.api import create_app; c=TestClient(create_app()); r=c.get('/health'); print(r.status_code==200 and r.json().get('status')=='ok')"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "api run endpoint maps unknown transaction to http 404" {
  #R005: ValueError from service is converted into HTTP 404.
  #R005-T01: Verify /v1/matchy/runs returns 404 for unknown transaction.
  run env PYTHONPATH="$(pwd)" python3 -c "from fastapi.testclient import TestClient; import matchy.api as api; class StubService:
  def match_transaction(self, transaction_id, trigger_source='manual'):
   raise ValueError('Unknown transaction_id: missing'); old=api.MatchService; api.MatchService=lambda settings: StubService(); app=api.create_app(); api.MatchService=old; c=TestClient(app); r=c.post('/v1/matchy/runs', json={'transaction_ids':['missing'],'trigger_source':'manual'}); print(r.status_code==404)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
