#R001: Python test lane coverage for repository password requirement.
#R005: Python test lane coverage for session commit/rollback behavior.
#R010: Python test lane coverage for pending transaction discovery.
#R015: Python test lane coverage for last-run and active-match summaries.

from decimal import Decimal
from datetime import datetime, timezone
import inspect
from types import SimpleNamespace

from matchy.models import AiSelection, EmailCandidate, RankedCandidate
from matchy.repository import MatchRepository


def test_repository_initialization_fails_without_teller_db_password() -> None:
    #R001: Repository rejects missing teller_db_password.
    #R001-T01: Python test lane exists for password requirement.
    try:
        MatchRepository(SimpleNamespace(teller_db_password=""))
    except RuntimeError as exc:
        assert "TELLER_DB_PASSWORD is required" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_repository_session_context_commits_and_rollbacks_through_fake_session() -> None:
    #R005: Session context commits success and rollbacks on failure.
    #R005-T01: Python test lane exists for session context requirement.
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
    repo._write_enabled = True
    with repo.session():
        pass
    first = sessions[-1]
    assert first.commits == 1 and first.rollbacks == 0 and first.closed == 1
    try:
        with repo.session():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    second = sessions[-1]
    assert second.commits == 0 and second.rollbacks == 1 and second.closed == 1
    repo._write_enabled = False
    with repo.session():
        pass
    third = sessions[-1]
    assert third.commits == 0 and third.rollbacks == 1 and third.closed == 1


def test_repository_pending_transaction_query_returns_ordered_transaction_ids() -> None:
    #R010: Pending transaction id discovery returns string IDs from active-unmatched lookback query.
    #R010-T01: Python test lane exists for pending id discovery requirement.
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
    assert rows == ["txn_1", "txn_2"]


def test_repository_read_last_run_summary_returns_run_and_candidate_cache_rows() -> None:
    #R015: read_last_run_summary returns the newest run plus its persisted candidate payload rows.
    #R015-T01: Python test lane exists for last-run summary requirement.
    class FakeResult:
        def __init__(self, row=None, rows=None):
            self._row = row
            self._rows = rows or []

        def mappings(self):
            return self

        def fetchone(self):
            return self._row

        def all(self):
            return self._rows

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
    assert out == {
        "match_run_id": 42,
        "status": "succeeded",
        "model_name": "claude-sonnet-4-5",
        "prompt_version": "v1",
        "candidate_cache_rows": [
            {
                "email_message_id": "m1",
                "email_received_at": "",
                "score": 0.0,
                "reason_json": {},
                "cached_subject": "",
                "cached_sender": "",
                "cached_snippet": "",
                "is_unmatched_email_priority": False,
            },
            {
                "email_message_id": "m2",
                "email_received_at": "",
                "score": 0.0,
                "reason_json": {},
                "cached_subject": "",
                "cached_sender": "",
                "cached_snippet": "",
                "is_unmatched_email_priority": False,
            },
        ],
    }
    assert empty is None


def test_repository_read_active_match_summary_returns_active_row_or_none() -> None:
    #R015: read_active_match_summary returns the active match row metadata for cache-hit responses.
    #R015-T02: Python test lane exists for active-match summary requirement.
    class FakeResult:
        def __init__(self, row):
            self._row = row

        def mappings(self):
            return self

        def fetchone(self):
            return self._row

    class FakeSession:
        def __init__(self, results):
            self._results = list(results)

        def execute(self, *_args, **_kwargs):
            return self._results.pop(0)

    session_with = FakeSession([FakeResult({
        "match_id": 7,
        "email_message_id": "m9",
        "state": "ai_match_confident",
        "ai_confidence": Decimal("0.9500"),
        "selected_by": "ai",
    })])
    session_empty = FakeSession([FakeResult(None)])
    repo = object.__new__(MatchRepository)
    out = repo.read_active_match_summary(session_with, "txn_1")
    empty = repo.read_active_match_summary(session_empty, "txn_missing")
    assert out == {
        "match_id": 7,
        "email_message_id": "m9",
        "state": "ai_match_confident",
        "selected_by": "ai",
        "ai_confidence": 0.95,
    }
    assert empty is None


def test_repository_pending_transaction_query_requeues_unsettled_but_skips_human_authoritative_rows() -> None:
    #R010: Pending discovery re-queues AI-only no-match and uncertain rows.
    #R010-T02: Python test lane exists for re-queue SQL predicate requirement.
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
    assert "ai_candidate_uncertain" in sql
    assert "ai_no_match_found" in sql
    assert "selected_by::text = 'ai'" in sql
    assert "tem.match_id IS NULL" in sql
    assert "latest_runs" in sql
    assert "OR lr.transaction_id IS NULL" in sql
    assert "COALESCE(lr.completed_at, lr.created_at" in sql
    assert "human_confirmed_ai_match" not in sql
    assert "human_overrode_ai_match" not in sql
    assert params == {"lookback_days": 14, "limit": 10}


def test_insert_human_confirmed_match_uses_settled_human_state() -> None:
    #R010-T02: Human confirmation persists the settled enum value used by pending-transaction filtering.
    source = inspect.getsource(MatchRepository.insert_human_confirmed_match)
    assert "human_confirmed_ai_match" in source


def test_persist_ai_result_avoids_duplicate_active_email_match_insert_and_marks_needs_review() -> None:
    #R015: If selected email already has an active match elsewhere, persist a NULL-email uncertain row.
    class CapturingSession:
        def __init__(self):
            self.calls = []

        def execute(self, statement, params=None):
            self.calls.append((str(statement), dict(params or {})))
            return SimpleNamespace()

    candidate = EmailCandidate(
        message_id="msg_dup",
        subject="s",
        preview="p",
        received_at=datetime(2026, 5, 24, tzinfo=timezone.utc),
        sender="x@y",
        body_text="body",
    )
    ranked = RankedCandidate(candidate=candidate, score=0.9, reasons={"reason": "r"})
    selection = AiSelection(
        selected_message_ids=["msg_dup"],
        confidence=0.95,
        uncertain=False,
        rationale="pick best",
        backend="anthropic",
        model_name="claude-sonnet-4-5",
    )
    repo = object.__new__(MatchRepository)
    repo.has_active_match = lambda session, email_message_id: True
    session = CapturingSession()
    selected = repo.persist_ai_result(
        session=session,
        transaction_id="txn_1",
        run_id=123,
        ranked_candidates=[ranked],
        ai_selection=selection,
        auto_confirm_threshold=0.9,
    )
    assert selected == []
    status_calls = [params for sql, params in session.calls if "UPDATE teller.transaction_email_match_run" in sql]
    assert status_calls and status_calls[-1]["status"] == "needs_review"
    uncertain_rows = [
        params
        for sql, params in session.calls
        if "INSERT INTO teller.transaction_email_match" in sql and "'ai_candidate_uncertain'" in sql and "email_message_id" not in params
    ]
    assert uncertain_rows and uncertain_rows[-1]["transaction_id"] == "txn_1"


def test_persist_ai_result_filters_out_of_set_ai_ids_to_no_match_found() -> None:
    #R015: AI ids outside ranked candidate set are treated as unselected to avoid empty-result active-row gaps.
    class CapturingSession:
        def __init__(self):
            self.calls = []

        def execute(self, statement, params=None):
            self.calls.append((str(statement), dict(params or {})))
            return SimpleNamespace()

    candidate = EmailCandidate(
        message_id="msg_valid",
        subject="s",
        preview="p",
        received_at=datetime(2026, 5, 24, tzinfo=timezone.utc),
        sender="x@y",
        body_text="body",
    )
    ranked = RankedCandidate(candidate=candidate, score=0.9, reasons={"reason": "r"})
    selection = AiSelection(
        selected_message_ids=["msg_out_of_set"],
        confidence=0.95,
        uncertain=False,
        rationale="invalid id",
        backend="anthropic",
        model_name="claude-sonnet-4-5",
    )
    repo = object.__new__(MatchRepository)
    repo.has_active_match = lambda session, email_message_id: False
    session = CapturingSession()
    selected = repo.persist_ai_result(
        session=session,
        transaction_id="txn_1",
        run_id=123,
        ranked_candidates=[ranked],
        ai_selection=selection,
        auto_confirm_threshold=0.9,
    )
    assert selected == []
    no_match_rows = [
        params
        for sql, params in session.calls
        if "INSERT INTO teller.transaction_email_match" in sql and "'ai_no_match_found'" in sql
    ]
    assert no_match_rows and no_match_rows[-1]["transaction_id"] == "txn_1"
    status_calls = [params for sql, params in session.calls if "UPDATE teller.transaction_email_match_run" in sql]
    assert status_calls and status_calls[-1]["status"] == "no_candidates"
