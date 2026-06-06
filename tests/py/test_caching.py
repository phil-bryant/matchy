#R020: Python test lane coverage for cache hit/miss paths.

from datetime import datetime, timezone
from decimal import Decimal

from matchy.ai_ranker import PROMPT_VERSION
from matchy.models import AiSelection, EmailCandidate, TransactionInput
from matchy.service import MatchService


def test_service_short_circuits_ai_call_when_candidate_set_is_unchanged_since_last_run() -> None:
    #R020: match_transaction returns skipped=True when (model, prompt, candidate set) match last run.
    #R020-T01: Python test lane exists for cache hit requirement.
    class FakeRepo:
        class Ctx:
            def __init__(self, session):
                self.session = session

            def __enter__(self):
                return self.session

            def __exit__(self, *exc):
                return False

        def __init__(self, txn, last_summary, active):
            self.txn = txn
            self.last_summary = last_summary
            self.active = active
            self.create_run_calls = 0

        def session(self):
            return FakeRepo.Ctx(object())

        def load_transaction(self, session, transaction_id):
            return self.txn

        def read_last_run_summary(self, session, transaction_id):
            return self.last_summary

        def read_active_match_summary(self, session, transaction_id):
            return self.active

        def create_run(self, **kwargs):
            self.create_run_calls += 1
            return 999

    class FakeClient:
        def __init__(self, results):
            self._results = results
            self.search_calls = 0

        def search_candidates(self, query, limit=75):
            self.search_calls += 1
            return self._results.pop(0) if self._results else []

        def get_message(self, _mid, timeout_seconds=None):
            return {}

    class FakeRanker:
        def __init__(self, model):
            self._model = model

        def planned_model_name(self):
            return self._model

        def select(self, txn, ranked):
            raise AssertionError("AI ranker must not be called on cache hit")

    txn = TransactionInput("txn1", "acc", Decimal("35.99"), datetime(2026, 5, 5, tzinfo=timezone.utc), "LYFT", "")
    cands = [
        EmailCandidate("m_a", "s", "p", datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "p"),
        EmailCandidate("m_b", "s", "p", datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "p"),
    ]
    repo = FakeRepo(
        txn,
        last_summary={
            "match_run_id": 50,
            "status": "succeeded",
            "model_name": "claude-sonnet-4-5",
            "prompt_version": PROMPT_VERSION,
            "candidate_message_ids": ["m_a", "m_b"],
        },
        active={
            "match_id": 50,
            "email_message_id": "m_a",
            "state": "ai_match_confident",
            "selected_by": "ai",
            "ai_confidence": 0.95,
        },
    )
    svc = object.__new__(MatchService)
    svc._settings = type("S", (), {
        "mailcart_body_enrichment_enabled": True,
        "mailcart_body_enrichment_limit": 75,
        "auto_confirm_threshold": 0.9,
    })()
    svc._repository = repo
    svc._mailcart_client = FakeClient([cands])
    svc._ai_ranker = FakeRanker("claude-sonnet-4-5")
    result = svc.match_transaction("txn1")
    assert result.get("skipped") is True
    assert result.get("run_id") == 50
    assert result.get("selected_message_ids") == ["m_a"]
    assert repo.create_run_calls == 0
    assert svc._mailcart_client.search_calls == 1


def test_service_runs_full_ai_pipeline_when_candidate_set_changes_since_last_run() -> None:
    #R020: Different candidate id set must defeat the cache and trigger a fresh evaluation.
    #R020-T02: Python test lane exists for cache miss requirement.
    class FakeRepo:
        class Ctx:
            def __init__(self, session):
                self.session = session

            def __enter__(self):
                return self.session

            def __exit__(self, *exc):
                return False

        def __init__(self, txn, last_summary):
            self.txn = txn
            self.last_summary = last_summary
            self.created = []
            self.persisted_with = None
            self.candidates_inserted = None

        def session(self):
            return FakeRepo.Ctx(_FakeSession())

        def load_transaction(self, session, transaction_id):
            return self.txn

        def read_last_run_summary(self, session, transaction_id):
            return self.last_summary

        def read_active_match_summary(self, session, transaction_id):
            return None

        def create_run(self, **kwargs):
            self.created.append(kwargs)
            return 101

        def update_run_model_name(self, **kwargs):
            pass

        def insert_candidates(self, **kwargs):
            self.candidates_inserted = kwargs

        def persist_ai_result(self, **kwargs):
            self.persisted_with = kwargs
            return list(kwargs["ai_selection"].selected_message_ids)

        def mark_run_failed(self, *a, **_k):
            pass

    class _FakeSession:
        def execute(self, *a, **_k):
            class R:
                def mappings(self):
                    return self

                def all(self):
                    return []

            return R()

    class FakeClient:
        def __init__(self, results):
            self._results = results

        def search_candidates(self, query, limit=75):
            return self._results.pop(0) if self._results else []

        def get_message(self, _mid, timeout_seconds=None):
            return {"text_body": "$35.99 fare"}

    class FakeRanker:
        def planned_model_name(self):
            return "claude-sonnet-4-5"

        def select(self, txn, ranked):
            return AiSelection(
                selected_message_ids=[ranked[0].candidate.message_id],
                confidence=0.95,
                uncertain=False,
                rationale="ok",
                backend="anthropic",
                model_name="claude-sonnet-4-5",
            )

    txn = TransactionInput("txn1", "acc", Decimal("35.99"), datetime(2026, 5, 5, tzinfo=timezone.utc), "LYFT", "")
    new_cands = [EmailCandidate("m_new", "subj", "preview", datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "preview")]
    repo = FakeRepo(
        txn,
        last_summary={
            "match_run_id": 50,
            "status": "succeeded",
            "model_name": "claude-sonnet-4-5",
            "prompt_version": PROMPT_VERSION,
            "candidate_message_ids": ["m_old"],
        },
    )
    svc = object.__new__(MatchService)
    svc._settings = type("S", (), {
        "mailcart_body_enrichment_enabled": True,
        "mailcart_body_enrichment_limit": 75,
        "auto_confirm_threshold": 0.9,
    })()
    svc._repository = repo
    svc._mailcart_client = FakeClient([new_cands])
    svc._ai_ranker = FakeRanker()
    result = svc.match_transaction("txn1")
    assert result.get("skipped") is False
    assert result["run_id"] == 101
    assert result["selected_message_ids"] == ["m_new"]
    assert len(repo.created) == 1
    assert repo.persisted_with is not None


def test_service_refuses_to_cache_hit_when_last_run_was_failed() -> None:
    #R020: Failed runs are never cache-eligible so transient errors self-heal on the next loop.
    #R020-T03: Python test lane exists for failed-run cache exclusion requirement.
    class FakeRepo:
        class Ctx:
            def __init__(self, session):
                self.session = session

            def __enter__(self):
                return self.session

            def __exit__(self, *exc):
                return False

        def __init__(self, txn, last_summary):
            self.txn = txn
            self.last_summary = last_summary
            self.created = 0

        def session(self):
            return FakeRepo.Ctx(_FakeSession())

        def load_transaction(self, session, transaction_id):
            return self.txn

        def read_last_run_summary(self, session, transaction_id):
            return self.last_summary

        def read_active_match_summary(self, session, transaction_id):
            return None

        def create_run(self, **kwargs):
            self.created += 1
            return 200

        def update_run_model_name(self, **kwargs):
            pass

        def insert_candidates(self, **kwargs):
            pass

        def persist_ai_result(self, **kwargs):
            return list(kwargs["ai_selection"].selected_message_ids)

        def mark_run_failed(self, *a, **_k):
            pass

    class _FakeSession:
        def execute(self, *a, **_k):
            class R:
                def mappings(self):
                    return self

                def all(self):
                    return []

            return R()

    class FakeClient:
        def __init__(self, results):
            self._results = results

        def search_candidates(self, query, limit=75):
            return self._results.pop(0) if self._results else []

        def get_message(self, _mid, timeout_seconds=None):
            return {}

    class FakeRanker:
        def planned_model_name(self):
            return "claude-sonnet-4-5"

        def select(self, txn, ranked):
            return AiSelection(
                selected_message_ids=[],
                confidence=0.0,
                uncertain=True,
                rationale="no",
                backend="anthropic",
                model_name="claude-sonnet-4-5",
            )

    txn = TransactionInput("txn1", "acc", Decimal("35.99"), datetime(2026, 5, 5, tzinfo=timezone.utc), "LYFT", "")
    cands = [EmailCandidate("m_same", "s", "p", datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "p")]
    repo = FakeRepo(
        txn,
        last_summary={
            "match_run_id": 60,
            "status": "failed",
            "model_name": "claude-sonnet-4-5",
            "prompt_version": PROMPT_VERSION,
            "candidate_message_ids": ["m_same"],
        },
    )
    svc = object.__new__(MatchService)
    svc._settings = type("S", (), {
        "mailcart_body_enrichment_enabled": True,
        "mailcart_body_enrichment_limit": 75,
        "auto_confirm_threshold": 0.9,
    })()
    svc._repository = repo
    svc._mailcart_client = FakeClient([cands])
    svc._ai_ranker = FakeRanker()
    result = svc.match_transaction("txn1")
    assert result.get("skipped") is False
    assert repo.created == 1


def test_service_refuses_to_cache_hit_when_active_state_is_ai_no_match_found() -> None:
    #R020: ai_no_match_found states must be re-evaluated even when candidate hash/model/prompt match.
    class FakeRepo:
        class Ctx:
            def __init__(self, session):
                self.session = session

            def __enter__(self):
                return self.session

            def __exit__(self, *exc):
                return False

        def __init__(self, txn, last_summary, active):
            self.txn = txn
            self.last_summary = last_summary
            self.active = active
            self.created = 0

        def session(self):
            return FakeRepo.Ctx(_FakeSession())

        def load_transaction(self, session, transaction_id):
            return self.txn

        def read_last_run_summary(self, session, transaction_id):
            return self.last_summary

        def read_active_match_summary(self, session, transaction_id):
            return self.active

        def create_run(self, **kwargs):
            self.created += 1
            return 201

        def update_run_model_name(self, **kwargs):
            pass

        def insert_candidates(self, **kwargs):
            pass

        def persist_ai_result(self, **kwargs):
            return []

        def mark_run_failed(self, *a, **_k):
            pass

    class _FakeSession:
        def execute(self, *a, **_k):
            class R:
                def mappings(self):
                    return self

                def all(self):
                    return []

            return R()

    class FakeClient:
        def __init__(self, results):
            self._results = results

        def search_candidates(self, query, limit=75):
            return self._results.pop(0) if self._results else []

        def get_message(self, _mid, timeout_seconds=None):
            return {}

    class FakeRanker:
        def planned_model_name(self):
            return "claude-sonnet-4-5"

        def select(self, txn, ranked):
            return AiSelection(
                selected_message_ids=[],
                confidence=0.0,
                uncertain=True,
                rationale="retry-no-match",
                backend="anthropic",
                model_name="claude-sonnet-4-5",
            )

    txn = TransactionInput("txn1", "acc", Decimal("35.99"), datetime(2026, 5, 5, tzinfo=timezone.utc), "LYFT", "")
    cands = [EmailCandidate("m_same", "s", "p", datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "p")]
    repo = FakeRepo(
        txn,
        last_summary={
            "match_run_id": 70,
            "status": "succeeded",
            "model_name": "claude-sonnet-4-5",
            "prompt_version": PROMPT_VERSION,
            "candidate_message_ids": ["m_same"],
        },
        active={
            "match_id": 70,
            "email_message_id": None,
            "state": "ai_no_match_found",
            "selected_by": "ai",
            "ai_confidence": 0.0,
        },
    )
    svc = object.__new__(MatchService)
    svc._settings = type("S", (), {
        "mailcart_body_enrichment_enabled": True,
        "mailcart_body_enrichment_limit": 75,
        "auto_confirm_threshold": 0.9,
    })()
    svc._repository = repo
    svc._mailcart_client = FakeClient([cands])
    svc._ai_ranker = FakeRanker()
    result = svc.match_transaction("txn1")
    assert result.get("skipped") is False
    assert repo.created == 1
