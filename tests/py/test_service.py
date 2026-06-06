#R001: Python test lane coverage for unknown transaction errors.
#R010: Python test lane coverage for pending matcher delegation.
#R025: Python test lane coverage for batch failure tolerance.
#R030: Python test lane coverage for concurrent pending batch behavior.
#R045: Python test lane coverage for human confirm delegation.

import logging
from types import SimpleNamespace

from matchy.cldr_cache import CldrCurrencyMatcher
from matchy.service import MatchService


def test_service_raises_valueerror_for_unknown_transactions() -> None:
    #R001: Unknown transaction IDs raise ValueError.
    #R001-T01: Python test lane exists for unknown transaction requirement.
    class Repo:
        class Ctx:
            #R001: Test helper supports this requirement-focused scenario.
            def __enter__(self):
                return object()

            #R001: Test helper supports this requirement-focused scenario.
            def __exit__(self, _exc_type, exc, _tb):
                return False

        #R001: Test helper supports this requirement-focused scenario.
        def session(self):
            return Repo.Ctx()

        #R001: Test helper supports this requirement-focused scenario.
        def load_transaction(self, session, transaction_id):
            return None

    service = object.__new__(MatchService)
    service._repository = Repo()
    try:
        service.match_transaction("missing")
    except ValueError as exc:
        assert "Unknown transaction_id" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_service_match_transactions_atomic_commits_once_for_successful_batch() -> None:
    #R300-T01: Verifies atomic batch commits once for a fully successful run.
    class Repo:
        class Ctx:
            #R300: Test double supports atomic batch commit behavior assertions.
            def __init__(self, repo):
                self._repo = repo

            #R300: Test double supports atomic batch commit behavior assertions.
            def __enter__(self):
                return self._repo.session_obj

            #R300: Test double supports atomic batch commit behavior assertions.
            def __exit__(self, exc_type, _exc, _tb):
                if exc_type is None:
                    self._repo.commits += 1
                else:
                    self._repo.rollbacks += 1
                return False

        #R300: Test double supports atomic batch commit behavior assertions.
        def __init__(self):
            self.session_obj = object()
            self.commits = 0
            self.rollbacks = 0

        #R300: Test double supports atomic batch commit behavior assertions.
        def session(self):
            return Repo.Ctx(self)

    repo = Repo()
    svc = object.__new__(MatchService)
    svc._repository = repo
    calls = []

    #R300: Test double supports atomic batch commit behavior assertions.
    def fake_match_transaction(transaction_id, trigger_source="manual", force_rematch=False, *, session=None, record_failure=True):
        calls.append((transaction_id, trigger_source, force_rematch, session, record_failure))
        return {"transaction_id": transaction_id}

    svc.match_transaction = fake_match_transaction

    rows = svc.match_transactions_atomic(["txn_1", "txn_2"], trigger_source="retry", force_rematch=True)

    assert rows == [{"transaction_id": "txn_1"}, {"transaction_id": "txn_2"}]
    assert repo.commits == 1
    assert repo.rollbacks == 0
    assert calls[0][3] is repo.session_obj
    assert calls[1][3] is repo.session_obj
    assert calls[0][4] is False
    assert calls[1][4] is False


def test_service_match_transactions_atomic_rolls_back_batch_on_failure() -> None:
    #R305-T01: Verifies atomic batch rolls back and re-raises on failure.
    class Repo:
        class Ctx:
            #R305: Test double supports atomic batch rollback behavior assertions.
            def __init__(self, repo):
                self._repo = repo

            #R305: Test double supports atomic batch rollback behavior assertions.
            def __enter__(self):
                return self._repo.session_obj

            #R305: Test double supports atomic batch rollback behavior assertions.
            def __exit__(self, exc_type, _exc, _tb):
                if exc_type is None:
                    self._repo.commits += 1
                else:
                    self._repo.rollbacks += 1
                return False

        #R305: Test double supports atomic batch rollback behavior assertions.
        def __init__(self):
            self.session_obj = object()
            self.commits = 0
            self.rollbacks = 0

        #R305: Test double supports atomic batch rollback behavior assertions.
        def session(self):
            return Repo.Ctx(self)

    repo = Repo()
    svc = object.__new__(MatchService)
    svc._repository = repo
    calls = []

    #R305: Test double supports atomic batch rollback behavior assertions.
    def fake_match_transaction(transaction_id, trigger_source="manual", force_rematch=False, *, session=None, record_failure=True):
        calls.append((transaction_id, session, record_failure))
        if transaction_id == "txn_2":
            raise ValueError("Unknown transaction_id: txn_2")
        return {"transaction_id": transaction_id}

    svc.match_transaction = fake_match_transaction

    try:
        svc.match_transactions_atomic(["txn_1", "txn_2"])
    except ValueError as exc:
        assert "txn_2" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert repo.commits == 0
    assert repo.rollbacks == 1
    assert calls[0][1] is repo.session_obj
    assert calls[1][1] is repo.session_obj
    assert calls[0][2] is False
    assert calls[1][2] is False


def test_service_initialization_runs_mailcart_startup_preflight_once(monkeypatch) -> None:
    #R310-T01: Verifies startup preflight runs exactly once when enabled.
    # Constructor wiring: MatchService.__init__ triggers Mailcart startup preflight when enabled.
    import matchy.service as service_module

    calls = {"preflight": 0}

    class StubMailcartClient:
        #R310: Test double supports startup preflight-once behavior assertions.
        def __init__(self, _settings):
            pass

        #R310: Test double supports startup preflight-once behavior assertions.
        def startup_preflight_healthcheck(self):
            calls["preflight"] += 1

    class StubCldrCache:
        #R310: Test double supports startup preflight-once behavior assertions.
        def __init__(self, _settings):
            pass

        #R310: Test double supports startup preflight-once behavior assertions.
        def currency_matcher(self):
            return CldrCurrencyMatcher([])

    monkeypatch.setattr(service_module, "MatchRepository", lambda settings: object())
    monkeypatch.setattr(service_module, "MailcartClient", StubMailcartClient)
    monkeypatch.setattr(service_module, "AiRanker", lambda settings: object())
    monkeypatch.setattr(service_module, "CldrCurrenciesCache", StubCldrCache)

    settings = SimpleNamespace(mailcart_startup_healthcheck_enabled=True, mailcart_failure_cooldown_seconds=15)
    service_module.MatchService(settings)
    assert calls["preflight"] == 1


def test_service_pending_matcher_tolerates_per_transaction_failures() -> None:
    #R025: One transaction's exception must not abort the whole batch.
    #R025-T01: Python test lane exists for batch failure tolerance requirement.
    logging.getLogger("matchy.service").setLevel(logging.CRITICAL)

    class Repo:
        class Ctx:
            #R025: Test helper supports this requirement-focused scenario.
            def __enter__(self):
                return object()

            #R025: Test helper supports this requirement-focused scenario.
            def __exit__(self, *exc):
                return False

        #R025: Test helper supports this requirement-focused scenario.
        def session(self):
            return Repo.Ctx()

        #R025: Test helper supports this requirement-focused scenario.
        def list_pending_transaction_ids(self, session, limit=100, lookback_days=14):
            return ["txn_a", "txn_b", "txn_c"]

    service = object.__new__(MatchService)
    service._repository = Repo()

    #R025: Test helper supports this requirement-focused scenario.
    def flaky_match_transaction(transaction_id, trigger_source="manual", force_rematch=False):
        if transaction_id == "txn_b":
            raise RuntimeError("anthropic 429")
        return {"transaction_id": transaction_id, "selected_message_ids": ["m_" + transaction_id]}

    service.match_transaction = flaky_match_transaction
    rows = service.match_pending_transactions(limit=3, lookback_days=14, trigger_source="auto")
    assert len(rows) == 3
    assert rows[0]["selected_message_ids"] == ["m_txn_a"]
    assert rows[1].get("error") == "anthropic 429"
    assert rows[1]["selected_message_ids"] == []
    assert rows[2]["selected_message_ids"] == ["m_txn_c"]


def test_service_pending_matcher_loads_pending_ids_then_runs_each_transaction() -> None:
    #R010: Pending matcher uses repository discovery and runs match_transaction for each pending transaction id.
    #R010-T01: Python test lane exists for pending matcher requirement.
    #R030-T01: Python test lane exists for concurrent pending matcher requirement.
    class Repo:
        class Ctx:
            #R010: Test helper supports this requirement-focused scenario.
            def __enter__(self):
                return object()

            #R010: Test helper supports this requirement-focused scenario.
            def __exit__(self, _exc_type, exc, _tb):
                return False

        #R010: Test helper supports this requirement-focused scenario.
        def session(self):
            return Repo.Ctx()

        #R010: Test helper supports this requirement-focused scenario.
        def list_pending_transaction_ids(self, session, limit=100, lookback_days=14):
            return ["txn_1", "txn_2"]

    service = object.__new__(MatchService)
    service._repository = Repo()
    calls = []

    #R010: Test helper supports this requirement-focused scenario.
    def fake_match_transaction(transaction_id, trigger_source="manual", force_rematch=False):
        calls.append((transaction_id, trigger_source))
        return {"transaction_id": transaction_id, "trigger_source": trigger_source}

    service.match_transaction = fake_match_transaction
    rows = service.match_pending_transactions(limit=9, lookback_days=2, trigger_source="auto")
    assert len(rows) == 2
    assert sorted(calls) == [("txn_1", "auto"), ("txn_2", "auto")]


def test_service_confirm_match_delegates_to_repository() -> None:
    #R045-T01: confirm_match deactivates prior active row, inserts human-confirmed row, and returns match_id.
    calls = []
    moved = []

    class FakeRepo:
        class Ctx:
            #R045: Test helper supports this requirement-focused scenario.
            def __enter__(self): return object()
            #R045: Test helper supports this requirement-focused scenario.
            def __exit__(self, *a): return False
        #R045: Test helper supports this requirement-focused scenario.
        def session(self): return FakeRepo.Ctx()
        #R045: Test helper supports this requirement-focused scenario.
        def deactivate_active_match(self, _s, txn): calls.append(("deact", txn))
        #R045: Test helper supports this requirement-focused scenario.
        def insert_human_confirmed_match(self, _s, txn, eml, note):
            calls.append(("insert", txn, eml, note))
            return 321

    class FakeMailcartClient:
        #R045: Test helper supports this requirement-focused scenario.
        def move_to_matchy(self, message_id):
            moved.append(message_id)
            return True

    service = object.__new__(MatchService)
    service._repository = FakeRepo()
    service._mailcart_client = FakeMailcartClient()
    service._settings = SimpleNamespace(email_move_enabled=True, write_enabled=True)
    result = service.confirm_match("t123", "e456", "note")
    assert calls == [("deact", "t123"), ("insert", "t123", "e456", "note")]
    assert moved == ["e456"]
    assert result == {"status": "confirmed", "match_id": 321}
