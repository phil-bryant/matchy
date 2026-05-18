#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

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
