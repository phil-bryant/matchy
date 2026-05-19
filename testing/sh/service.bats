#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01

@test "service raises valueerror for unknown transactions" {
  #R001: Unknown transaction IDs raise ValueError.
  #R001-T01: Verify error path when repository returns no transaction.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.service import MatchService

class Repo:
    class Ctx:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    def session(self):
        return Repo.Ctx()

    def load_transaction(self, session, transaction_id):
        return None

service = object.__new__(MatchService)
service._repository = Repo()
ok = False
try:
    service.match_transaction("missing")
except ValueError as exc:
    ok = "Unknown transaction_id" in str(exc)
print(ok)
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service query builders normalize and filter tokens" {
  #R005: Query helpers produce deterministic normalized text tokens.
  #R005-T01: Verify normalized query and broad query outputs.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.service import MatchService

service = object.__new__(MatchService)
query = service._build_query("Payment #1234 at DoorDash.com", "DoorDash")
broad = service._build_broad_query("Payment #1234 at DoorDash.com", "DoorDash")
print(query == "doordash payment doordash" and broad == "payment")
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service pending matcher loads pending ids then runs each transaction" {
  #R010: Pending matcher uses repository discovery and runs match_transaction for each pending transaction id.
  #R010-T01: Verify pending list is read once and each transaction id is delegated to match_transaction.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.service import MatchService

class Repo:
    class Ctx:
        def __enter__(self):
            return object()
        def __exit__(self, exc_type, exc, tb):
            return False
    def session(self):
        return Repo.Ctx()
    def list_pending_transaction_ids(self, session, limit=100, lookback_days=14):
        return ["txn_1", "txn_2"]

service = object.__new__(MatchService)
service._repository = Repo()
calls = []
def fake_match_transaction(transaction_id, trigger_source="manual"):
    calls.append((transaction_id, trigger_source))
    return {"transaction_id": transaction_id, "trigger_source": trigger_source}
service.match_transaction = fake_match_transaction
rows = service.match_pending_transactions(limit=9, lookback_days=2, trigger_source="auto")
print(len(rows) == 2 and calls == [("txn_1", "auto"), ("txn_2", "auto")])
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
