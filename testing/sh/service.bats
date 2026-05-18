#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

@test "service raises valueerror for unknown transactions" {
  #R001: Unknown transaction IDs raise ValueError.
  #R001-T01: Verify error path when repository returns no transaction.
  run env PYTHONPATH="$(pwd)" python3 -c "from matchy.service import MatchService; svc=object.__new__(MatchService); class Repo:
  class Ctx:
   def __enter__(self): return object()
   def __exit__(self, exc_type, exc, tb): return False
  def session(self): return Repo.Ctx()
  def load_transaction(self, session, transaction_id): return None
svc._repository=Repo(); ok=False
try:
 svc.match_transaction('missing')
except ValueError as exc:
 ok='Unknown transaction_id' in str(exc)
print(ok)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "service query builders normalize and filter tokens" {
  #R005: Query helpers produce deterministic normalized text tokens.
  #R005-T01: Verify normalized query and broad query outputs.
  run env PYTHONPATH="$(pwd)" python3 -c "from matchy.service import MatchService; svc=object.__new__(MatchService); q=svc._build_query('Payment #1234 at DoorDash.com','DoorDash'); b=svc._build_broad_query('Payment #1234 at DoorDash.com','DoorDash'); print(q=='payment doordash doordashcom' and b=='payment')"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
