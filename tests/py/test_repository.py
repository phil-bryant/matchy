#R001: Python test lane coverage for repository password requirement.
#R005: Python test lane coverage for session commit/rollback behavior.
#R010: Python test lane coverage for pending transaction discovery.
#R015: Python test lane coverage for last-run and active-match summaries.

from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
import inspect
from types import SimpleNamespace

from matchy.models import AiSelection, EmailCandidate, RankedCandidate
from matchy.repository import MatchRepository


def test_repository_binds_to_profile_driven_teller_engine(monkeypatch) -> None:
    #R001: Repository binds to teller's profile-driven engine (postgres or sqlite).
    #R001-T01: Python test lane exists for profile-driven engine binding.
    sentinel_engine = object()
    monkeypatch.setattr("matchy.repository.get_engine", lambda: sentinel_engine)
    repository = MatchRepository(SimpleNamespace(write_enabled=True))
    assert repository._engine is sentinel_engine
    assert repository._write_enabled is True


def test_repository_session_context_commits_and_rollbacks_through_fake_session() -> None:
    #R005: Session context commits success and rollbacks on failure.
    #R005-T01: Python test lane exists for session context requirement.
    class FakeSession:
        #R005: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            self.closed = 0

        #R005: Test helper supports this requirement-focused scenario.
        def commit(self):
            self.commits += 1

        #R005: Test helper supports this requirement-focused scenario.
        def rollback(self):
            self.rollbacks += 1

        #R005: Test helper supports this requirement-focused scenario.
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
        #R010: Test helper supports this requirement-focused scenario.
        def mappings(self):
            return self

        #R010: Test helper supports this requirement-focused scenario.
        def all(self):
            return [{"transaction_id": "txn_1"}, {"transaction_id": "txn_2"}]

    class FakeSession:
        #R010: Test helper supports this requirement-focused scenario.
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    repo = object.__new__(MatchRepository)
    rows = repo.list_pending_transaction_ids(FakeSession(), limit=4, lookback_days=3)
    assert rows == ["txn_1", "txn_2"]


def test_repository_read_last_run_summary_returns_run_and_candidate_cache_rows() -> None:
    #R015: read_last_run_summary returns the newest run plus its persisted candidate payload rows.
    #R015-T01: Python test lane exists for last-run summary requirement.
    class FakeResult:
        #R015: Test helper supports this requirement-focused scenario.
        def __init__(self, row=None, rows=None):
            self._row = row
            self._rows = rows or []

        #R015: Test helper supports this requirement-focused scenario.
        def mappings(self):
            return self

        #R015: Test helper supports this requirement-focused scenario.
        def fetchone(self):
            return self._row

        #R015: Test helper supports this requirement-focused scenario.
        def all(self):
            return self._rows

    class FakeSession:
        #R015: Test helper supports this requirement-focused scenario.
        def __init__(self, results):
            self._results = list(results)

        #R015: Test helper supports this requirement-focused scenario.
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
        #R015: Test helper supports this requirement-focused scenario.
        def __init__(self, row):
            self._row = row

        #R015: Test helper supports this requirement-focused scenario.
        def mappings(self):
            return self

        #R015: Test helper supports this requirement-focused scenario.
        def fetchone(self):
            return self._row

    class FakeSession:
        #R015: Test helper supports this requirement-focused scenario.
        def __init__(self, results):
            self._results = list(results)

        #R015: Test helper supports this requirement-focused scenario.
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
        #R010: Test helper supports this requirement-focused scenario.
        def mappings(self):
            return self

        #R010: Test helper supports this requirement-focused scenario.
        def all(self):
            return []

    class CapturingSession:
        #R010: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.statements = []

        #R010: Test helper supports this requirement-focused scenario.
        def execute(self, statement, params=None):
            self.statements.append((str(statement), dict(params or {})))
            return FakeResult()

    repo = object.__new__(MatchRepository)
    session = CapturingSession()
    repo.list_pending_transaction_ids(session, limit=10, lookback_days=14)
    sql, params = session.statements[0]
    assert "ai_candidate_uncertain" in sql
    assert "ai_no_match_found" in sql
    assert "CAST(tem.selected_by AS TEXT) = 'ai'" in sql
    assert "tem.match_id IS NULL" in sql
    assert "latest_runs" in sql
    assert "OR lr.transaction_id IS NULL" in sql
    assert "COALESCE(lr.completed_at, lr.created_at" in sql
    assert "human_confirmed_ai_match" not in sql
    assert "human_overrode_ai_match" not in sql
    #R010: Portable cutoff/epoch values are bound instead of Postgres interval math.
    assert params["limit"] == 10
    assert params["epoch"] == "1970-01-01 00:00:00"
    expected_cutoff = (date.today() - timedelta(days=14)).isoformat()
    assert params["cutoff_date"] == expected_cutoff


def test_insert_human_confirmed_match_uses_settled_human_state() -> None:
    #R010-T02: Human confirmation persists the settled enum value used by pending-transaction filtering.
    source = inspect.getsource(MatchRepository.insert_human_confirmed_match)
    assert "human_confirmed_ai_match" in source


def test_persist_ai_result_avoids_duplicate_active_email_match_insert_and_marks_needs_review() -> None:
    #R015: If selected email already has an active match elsewhere, persist a NULL-email uncertain row.
    class CapturingSession:
        #R015: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.calls = []

        #R015: Test helper supports this requirement-focused scenario.
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
    status_calls = [params for sql, params in session.calls if "UPDATE matchy.transaction_email_match_run" in sql]
    assert status_calls and status_calls[-1]["status"] == "needs_review"
    uncertain_rows = [
        params
        for sql, params in session.calls
        if "INSERT INTO matchy.transaction_email_match" in sql and "'ai_candidate_uncertain'" in sql and "email_message_id" not in params
    ]
    assert uncertain_rows and uncertain_rows[-1]["transaction_id"] == "txn_1"


def test_persist_ai_result_filters_out_of_set_ai_ids_to_no_match_found() -> None:
    #R015: AI ids outside ranked candidate set are treated as unselected to avoid empty-result active-row gaps.
    class CapturingSession:
        #R015: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.calls = []

        #R015: Test helper supports this requirement-focused scenario.
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
        if "INSERT INTO matchy.transaction_email_match" in sql and "'ai_no_match_found'" in sql
    ]
    assert no_match_rows and no_match_rows[-1]["transaction_id"] == "txn_1"
    status_calls = [params for sql, params in session.calls if "UPDATE matchy.transaction_email_match_run" in sql]
    assert status_calls and status_calls[-1]["status"] == "no_candidates"


def test_repository_load_transaction_maps_db_row_to_transaction_input_or_none() -> None:
    #R720-T01: load_transaction returns TransactionInput mapped from SQL row or None when no row exists.
    class FakeResult:
        #R720: Plain reuse tag for row-mapping scaffolding in load_transaction tests.
        def __init__(self, row):
            self._row = row

        #R720: Plain reuse tag for result-wrapper scaffolding in load_transaction tests.
        def mappings(self):
            return self

        #R720: Plain reuse tag for row-fetch scaffolding in load_transaction tests.
        def fetchone(self):
            return self._row

    class FakeSession:
        #R720: Plain reuse tag for fake-session constructor scaffolding in load_transaction tests.
        def __init__(self, row):
            self._row = row

        #R720: Plain reuse tag for execute scaffolding in load_transaction tests.
        def execute(self, *_args, **_kwargs):
            return FakeResult(self._row)

    repo = object.__new__(MatchRepository)
    row = {
        "transaction_id": "txn_1",
        "account_id": "acc_1",
        "amount": Decimal("42.55"),
        "date_value": datetime(2026, 6, 1, 9, 30, 0),
        "description": "Coffee Shop",
        "counterparty_name": "Coffee Shop",
    }
    mapped = repo.load_transaction(FakeSession(row), "txn_1")
    missing = repo.load_transaction(FakeSession(None), "txn_missing")
    assert mapped is not None
    assert mapped.transaction_id == "txn_1"
    assert mapped.amount == Decimal("42.55")
    assert mapped.date.tzinfo == timezone.utc
    assert missing is None


def test_repository_create_run_returns_inserted_match_run_id() -> None:
    #R721-T01: create_run inserts needs_review run rows and returns the generated run id.
    class FakeResult:
        #R721: Plain reuse tag for scalar result scaffolding in create_run tests.
        def scalar_one(self):
            return 321

    class FakeSession:
        #R721: Plain reuse tag for fake-session constructor scaffolding in create_run tests.
        def __init__(self):
            self.calls = []

        #R721: Plain reuse tag for execute scaffolding in create_run tests.
        def execute(self, statement, params):
            self.calls.append((str(statement), dict(params)))
            return FakeResult()

    session = FakeSession()
    repo = object.__new__(MatchRepository)
    run_id = repo.create_run(session, "txn_1", "manual", "claude-sonnet-4-5", "v3")
    assert run_id == 321
    sql, params = session.calls[0]
    assert "INSERT INTO matchy.transaction_email_match_run" in sql
    assert params["transaction_id"] == "txn_1"
    assert params["trigger_source"] == "manual"


def test_repository_update_run_model_name_executes_targeted_update() -> None:
    #R722-T01: update_run_model_name updates only model_name for the selected run id.
    class FakeSession:
        #R722: Plain reuse tag for fake-session constructor scaffolding in update_run_model_name tests.
        def __init__(self):
            self.calls = []

        #R722: Plain reuse tag for execute scaffolding in update_run_model_name tests.
        def execute(self, statement, params):
            self.calls.append((str(statement), dict(params)))
            return SimpleNamespace()

    session = FakeSession()
    repo = object.__new__(MatchRepository)
    repo.update_run_model_name(session, 44, "claude-sonnet-4-5")
    sql, params = session.calls[0]
    assert "UPDATE matchy.transaction_email_match_run" in sql
    assert params == {"model_name": "claude-sonnet-4-5", "match_run_id": 44}


def test_repository_lists_active_email_ids_for_other_transactions() -> None:
    #R723-T01: list_active_email_ids_for_other_transactions returns a set of active email ids excluding the current transaction.
    class FakeResult:
        #R723: Plain reuse tag for result-wrapper scaffolding in active-email-id tests.
        def mappings(self):
            return self

        #R723: Plain reuse tag for row-list scaffolding in active-email-id tests.
        def all(self):
            return [{"email_message_id": "m1"}, {"email_message_id": "m2"}, {"email_message_id": "m1"}]

    class FakeSession:
        #R723: Plain reuse tag for execute scaffolding in active-email-id tests.
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    repo = object.__new__(MatchRepository)
    email_ids = repo.list_active_email_ids_for_other_transactions(FakeSession(), "txn_1")
    assert email_ids == {"m1", "m2"}


def test_repository_update_run_status_persists_status_completion_and_error() -> None:
    #R724-T01: _update_run_status writes status/error fields and stamps completed_at for the selected run.
    class FakeSession:
        #R724: Plain reuse tag for fake-session constructor scaffolding in update_run_status tests.
        def __init__(self):
            self.calls = []

        #R724: Plain reuse tag for execute scaffolding in update_run_status tests.
        def execute(self, statement, params):
            self.calls.append((str(statement), dict(params)))
            return SimpleNamespace()

    session = FakeSession()
    repo = object.__new__(MatchRepository)
    repo._update_run_status(session, 77, "failed", error_text="boom")
    sql, params = session.calls[0]
    assert "UPDATE matchy.transaction_email_match_run" in sql
    assert "completed_at = CURRENT_TIMESTAMP" in sql
    assert params == {"status": "failed", "error_text": "boom", "match_run_id": 77}


def test_repository_mark_run_failed_delegates_to_status_update_helper() -> None:
    #R725-T01: mark_run_failed delegates to _update_run_status with failed status and caller-provided error text.
    calls = []
    repo = object.__new__(MatchRepository)
    repo._update_run_status = lambda session, run_id, status, error_text=None: calls.append((session, run_id, status, error_text))
    marker_session = object()
    repo.mark_run_failed(marker_session, 12, "network timeout")
    assert calls == [(marker_session, 12, "failed", "network timeout")]
