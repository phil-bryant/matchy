#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01

@test "repository initialization fails without teller db password" {
  #R001: Repository rejects missing teller_db_password.
  #R001-T01: Verify RuntimeError when password is empty.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from types import SimpleNamespace
from matchy.repository import MatchRepository

ok = False
try:
    MatchRepository(SimpleNamespace(teller_db_password=""))
except RuntimeError as exc:
    ok = "TELLER_DB_PASSWORD is required" in str(exc)
print(ok)
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "repository session context commits and rollbacks through fake session" {
  #R005: Session context commits success and rollbacks on failure.
  #R005-T01: Verify commit/rollback behavior using fake session factory.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.repository import MatchRepository

class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1

repo = object.__new__(MatchRepository)
sessions = []
repo._session_factory = lambda: sessions.append(FakeSession()) or sessions[-1]

with repo.session():
    pass
first = sessions[-1]
ok = first.commits == 1 and first.rollbacks == 0 and first.closed == 1

try:
    with repo.session():
        raise RuntimeError("boom")
except RuntimeError:
    pass
second = sessions[-1]
print(ok and second.commits == 0 and second.rollbacks == 1 and second.closed == 1)
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "repository pending transaction query returns ordered transaction ids" {
  #R010: Pending transaction id discovery returns string IDs from active-unmatched lookback query.
  #R010-T01: Verify list_pending_transaction_ids reads rows and returns transaction_id values.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.repository import MatchRepository

class FakeResult:
    def mappings(self):
        return self
    def all(self):
        return [{"transaction_id": "txn_1"}, {"transaction_id": "txn_2"}]

class FakeSession:
    def execute(self, *_args, **_kwargs):
        return FakeResult()

repo = object.__new__(MatchRepository)
rows = repo.list_pending_transaction_ids(FakeSession(), limit=4, lookback_days=3)
print(rows == ["txn_1", "txn_2"])
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
