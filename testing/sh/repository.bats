#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R010-T02 #R015-T01 #R015-T02

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

@test "repository read_last_run_summary returns run + candidate id set" {
  #R015: read_last_run_summary returns the newest run plus its persisted candidate id set.
  #R015-T01: Verify the helper returns the run summary + candidate ids; returns None when no runs.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.repository import MatchRepository

class FakeResult:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []
    def mappings(self): return self
    def fetchone(self): return self._row
    def all(self): return self._rows

class FakeSession:
    def __init__(self, results):
        self._results = list(results)
    def execute(self, *_args, **_kwargs):
        return self._results.pop(0)

session_with_runs = FakeSession([
    FakeResult(row={"match_run_id": 42, "status": "succeeded", "model_name": "claude-sonnet-4-5", "prompt_version": "v1"}),
    FakeResult(rows=[{"email_message_id": "m1"}, {"email_message_id": "m2"}]),
])
session_empty = FakeSession([FakeResult(row=None)])
repo = object.__new__(MatchRepository)
out = repo.read_last_run_summary(session_with_runs, "txn_1")
empty = repo.read_last_run_summary(session_empty, "txn_missing")
checks = [
    out == {"match_run_id": 42, "status": "succeeded", "model_name": "claude-sonnet-4-5",
            "prompt_version": "v1", "candidate_message_ids": ["m1", "m2"]},
    empty is None,
]
print(all(checks))
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "repository read_active_match_summary returns active row or None" {
  #R015: read_active_match_summary returns the active match row metadata for cache-hit responses.
  #R015-T02: Verify it returns the dict shape and handles the no-active-row case.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from decimal import Decimal
from matchy.repository import MatchRepository

class FakeResult:
    def __init__(self, row):
        self._row = row
    def mappings(self): return self
    def fetchone(self): return self._row

class FakeSession:
    def __init__(self, results):
        self._results = list(results)
    def execute(self, *_args, **_kwargs):
        return self._results.pop(0)

session_with = FakeSession([FakeResult({"match_id": 7, "email_message_id": "m9", "state": "ai_match_confident",
                                        "ai_confidence": Decimal("0.9500"), "selected_by": "ai"})])
session_empty = FakeSession([FakeResult(None)])
repo = object.__new__(MatchRepository)
out = repo.read_active_match_summary(session_with, "txn_1")
empty = repo.read_active_match_summary(session_empty, "txn_missing")
checks = [
    out == {"match_id": 7, "email_message_id": "m9", "state": "ai_match_confident",
            "selected_by": "ai", "ai_confidence": 0.95},
    empty is None,
]
print(all(checks))
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "repository pending transaction query re-queues unsettled but skips human-authoritative rows" {
  #R010: Pending discovery re-queues AI-only no-match and uncertain rows.
  #R010-T02: Verify the SQL predicate includes the re-queue clauses for AI-only verdicts.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from matchy.repository import MatchRepository

class FakeResult:
    def mappings(self):
        return self
    def all(self):
        return []

class CapturingSession:
    def __init__(self):
        self.statements = []
    def execute(self, statement, params=None):
        self.statements.append((str(statement), dict(params or {})))
        return FakeResult()

repo = object.__new__(MatchRepository)
session = CapturingSession()
repo.list_pending_transaction_ids(session, limit=10, lookback_days=14)
sql, params = session.statements[0]
checks = [
    "ai_candidate_uncertain" in sql,
    "ai_no_match_found" in sql,
    "selected_by::text = 'ai'" in sql,
    "tem.match_id IS NULL" in sql,
    "human_confirmed_ai_match" not in sql,
    "human_overrode_ai_match" not in sql,
    params == {"lookback_days": 14, "limit": 10},
]
print(all(checks))
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
