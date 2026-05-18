#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

@test "repository initialization fails without teller db password" {
  #R001: Repository rejects missing teller_db_password.
  #R001-T01: Verify RuntimeError when password is empty.
  run env PYTHONPATH="$(pwd)" python3 -c "from matchy.repository import MatchRepository; from matchy.settings import Settings; ok=False
try:
 MatchRepository(Settings(teller_db_password=''))
except RuntimeError as exc:
 ok='TELLER_DB_PASSWORD is required' in str(exc)
print(ok)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "repository session context commits and rollbacks through fake session" {
  #R005: Session context commits success and rollbacks on failure.
  #R005-T01: Verify commit/rollback behavior using fake session factory.
  run env PYTHONPATH="$(pwd)" python3 -c "from matchy.repository import MatchRepository; class FakeSession:
  def __init__(self): self.commits=0; self.rollbacks=0; self.closed=0
  def commit(self): self.commits+=1
  def rollback(self): self.rollbacks+=1
  def close(self): self.closed+=1
repo=object.__new__(MatchRepository); holder=[]; repo._session_factory=lambda: holder.append(FakeSession()) or holder[-1]
with repo.session() as s:
 pass
a=holder[-1]; ok=(a.commits==1 and a.rollbacks==0 and a.closed==1)
try:
 with repo.session() as s:
  raise RuntimeError('boom')
except RuntimeError:
 pass
b=holder[-1]; print(ok and b.commits==0 and b.rollbacks==1 and b.closed==1)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
