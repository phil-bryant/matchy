#R020: Python test lane coverage for cache hit/miss paths.
#R520: Python test lane coverage for cache row normalization.
#R525: Python test lane coverage for order-independent candidate hashing.
#R530: Python test lane coverage for message-id hashing.

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
            #R020: Reuse-tagged scaffolding helper for context wrapper setup.
            def __init__(self, session):
                self.session = session

            #R020: Reuse-tagged scaffolding helper for context manager entry.
            def __enter__(self):
                return self.session

            #R020: Reuse-tagged scaffolding helper for context manager exit.
            def __exit__(self, *exc):
                return False

        #R020: Reuse-tagged scaffolding helper for fake repository constructor.
        def __init__(self, txn, last_summary, active):
            self.txn = txn
            self.last_summary = last_summary
            self.active = active
            self.create_run_calls = 0

        #R020: Reuse-tagged scaffolding helper for fake session creation.
        def session(self):
            return FakeRepo.Ctx(object())

        #R020: Reuse-tagged scaffolding helper for fake transaction loading.
        def load_transaction(self, session, transaction_id):
            return self.txn

        #R020: Reuse-tagged scaffolding helper for fake run summary lookup.
        def read_last_run_summary(self, session, transaction_id):
            return self.last_summary

        #R020: Reuse-tagged scaffolding helper for fake active match lookup.
        def read_active_match_summary(self, session, transaction_id):
            return self.active

        #R020: Reuse-tagged scaffolding helper for fake run creation.
        def create_run(self, **kwargs):
            self.create_run_calls += 1
            return 999

    class FakeClient:
        #R020: Reuse-tagged scaffolding helper for fake client constructor.
        def __init__(self, results):
            self._results = results
            self.search_calls = 0

        #R020: Reuse-tagged scaffolding helper for fake candidate search.
        def search_candidates(self, query, limit=75):
            self.search_calls += 1
            return self._results.pop(0) if self._results else []

        #R020: Reuse-tagged scaffolding helper for fake message fetch.
        def get_message(self, _mid, timeout_seconds=None):
            return {}

    class FakeRanker:
        #R020: Reuse-tagged scaffolding helper for fake ranker constructor.
        def __init__(self, model):
            self._model = model

        #R020: Reuse-tagged scaffolding helper for fake planned model.
        def planned_model_name(self):
            return self._model

        #R020: Reuse-tagged scaffolding helper for cache-hit guard.
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
            #R020: Reuse-tagged scaffolding helper for context wrapper setup.
            def __init__(self, session):
                self.session = session

            #R020: Reuse-tagged scaffolding helper for context manager entry.
            def __enter__(self):
                return self.session

            #R020: Reuse-tagged scaffolding helper for context manager exit.
            def __exit__(self, *exc):
                return False

        #R020: Reuse-tagged scaffolding helper for fake repository constructor.
        def __init__(self, txn, last_summary):
            self.txn = txn
            self.last_summary = last_summary
            self.created = []
            self.persisted_with = None
            self.candidates_inserted = None

        #R020: Reuse-tagged scaffolding helper for fake session creation.
        def session(self):
            return FakeRepo.Ctx(_FakeSession())

        #R020: Reuse-tagged scaffolding helper for fake transaction loading.
        def load_transaction(self, session, transaction_id):
            return self.txn

        #R020: Reuse-tagged scaffolding helper for fake run summary lookup.
        def read_last_run_summary(self, session, transaction_id):
            return self.last_summary

        #R020: Reuse-tagged scaffolding helper for fake active match lookup.
        def read_active_match_summary(self, session, transaction_id):
            return None

        #R020: Reuse-tagged scaffolding helper for fake run creation.
        def create_run(self, **kwargs):
            self.created.append(kwargs)
            return 101

        #R020: Reuse-tagged scaffolding helper for fake model update.
        def update_run_model_name(self, **kwargs):
            pass

        #R020: Reuse-tagged scaffolding helper for fake candidate insertion.
        def insert_candidates(self, **kwargs):
            self.candidates_inserted = kwargs

        #R020: Reuse-tagged scaffolding helper for fake AI result persistence.
        def persist_ai_result(self, **kwargs):
            self.persisted_with = kwargs
            return list(kwargs["ai_selection"].selected_message_ids)

        #R020: Reuse-tagged scaffolding helper for fake failure marker.
        def mark_run_failed(self, *a, **_k):
            pass

    class _FakeSession:
        #R020: Reuse-tagged scaffolding helper for fake SQL execute behavior.
        def execute(self, *a, **_k):
            class R:
                #R020: Reuse-tagged scaffolding helper for fake mappings proxy.
                def mappings(self):
                    return self

                #R020: Reuse-tagged scaffolding helper for fake row list.
                def all(self):
                    return []

            return R()

    class FakeClient:
        #R020: Reuse-tagged scaffolding helper for fake client constructor.
        def __init__(self, results):
            self._results = results

        #R020: Reuse-tagged scaffolding helper for fake candidate search.
        def search_candidates(self, query, limit=75):
            return self._results.pop(0) if self._results else []

        #R020: Reuse-tagged scaffolding helper for fake message fetch.
        def get_message(self, _mid, timeout_seconds=None):
            return {"text_body": "$35.99 fare"}

    class FakeRanker:
        #R020: Reuse-tagged scaffolding helper for fake planned model.
        def planned_model_name(self):
            return "claude-sonnet-4-5"

        #R020: Reuse-tagged scaffolding helper for fake AI selection output.
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


def test_candidate_cache_rows_include_metadata_and_reason_fields() -> None:
    #R520: Cache row normalization preserves metadata and reason fields for hash comparison.
    #R520-T01: Python test lane exists for cache-row normalization requirement.
    service = object.__new__(MatchService)
    candidate = EmailCandidate("m1", "subject", "preview", datetime(2026, 5, 5, tzinfo=timezone.utc), "sender@example.com", "body")
    ranked = [type("Ranked", (), {"candidate": candidate, "score": 0.91, "reasons": {"unmatched_email_priority": True}})()]
    rows = service._ranked_candidate_cache_rows(ranked)
    assert rows[0]["email_message_id"] == "m1"
    assert rows[0]["cached_subject"] == "subject"
    assert rows[0]["cached_sender"] == "sender@example.com"
    assert rows[0]["is_unmatched_email_priority"] is True


def test_candidate_set_hash_is_order_independent_for_equivalent_rows() -> None:
    #R525: Candidate payload hashes are stable regardless of row order.
    #R525-T01: Python test lane exists for order-independent candidate hashing.
    rows_a = [
        {"email_message_id": "a", "email_received_at": "2026-01-01T00:00:00+00:00", "score": 0.5, "reason_json": {}, "cached_subject": "s1", "cached_sender": "x", "cached_snippet": "p1", "is_unmatched_email_priority": False},
        {"email_message_id": "b", "email_received_at": "2026-01-01T00:00:01+00:00", "score": 0.6, "reason_json": {}, "cached_subject": "s2", "cached_sender": "y", "cached_snippet": "p2", "is_unmatched_email_priority": True},
    ]
    rows_b = [rows_a[1], rows_a[0]]
    assert MatchService._candidate_set_hash(rows_a) == MatchService._candidate_set_hash(rows_b)


def test_candidate_message_id_hash_sorts_ids_before_digest() -> None:
    #R530: Message-id fallback hash is deterministic independent of input order.
    #R530-T01: Python test lane exists for message-id hashing requirement.
    first = MatchService._candidate_message_id_hash(["b", "a", "c"])
    second = MatchService._candidate_message_id_hash(["c", "b", "a"])
    assert first == second


def test_service_refuses_to_cache_hit_when_last_run_was_failed() -> None:
    #R020: Failed runs are never cache-eligible so transient errors self-heal on the next loop.
    #R020-T03: Python test lane exists for failed-run cache exclusion requirement.
    class FakeRepo:
        class Ctx:
            #R020: Reuse-tagged scaffolding helper for context wrapper setup.
            def __init__(self, session):
                self.session = session

            #R020: Reuse-tagged scaffolding helper for context manager entry.
            def __enter__(self):
                return self.session

            #R020: Reuse-tagged scaffolding helper for context manager exit.
            def __exit__(self, *exc):
                return False

        #R020: Reuse-tagged scaffolding helper for fake repository constructor.
        def __init__(self, txn, last_summary):
            self.txn = txn
            self.last_summary = last_summary
            self.created = 0

        #R020: Reuse-tagged scaffolding helper for fake session creation.
        def session(self):
            return FakeRepo.Ctx(_FakeSession())

        #R020: Reuse-tagged scaffolding helper for fake transaction loading.
        def load_transaction(self, session, transaction_id):
            return self.txn

        #R020: Reuse-tagged scaffolding helper for fake run summary lookup.
        def read_last_run_summary(self, session, transaction_id):
            return self.last_summary

        #R020: Reuse-tagged scaffolding helper for fake active match lookup.
        def read_active_match_summary(self, session, transaction_id):
            return None

        #R020: Reuse-tagged scaffolding helper for fake run creation.
        def create_run(self, **kwargs):
            self.created += 1
            return 200

        #R020: Reuse-tagged scaffolding helper for fake model update.
        def update_run_model_name(self, **kwargs):
            pass

        #R020: Reuse-tagged scaffolding helper for fake candidate insertion.
        def insert_candidates(self, **kwargs):
            pass

        #R020: Reuse-tagged scaffolding helper for fake AI result persistence.
        def persist_ai_result(self, **kwargs):
            return list(kwargs["ai_selection"].selected_message_ids)

        #R020: Reuse-tagged scaffolding helper for fake failure marker.
        def mark_run_failed(self, *a, **_k):
            pass

    class _FakeSession:
        #R020: Reuse-tagged scaffolding helper for fake SQL execute behavior.
        def execute(self, *a, **_k):
            class R:
                #R020: Reuse-tagged scaffolding helper for fake mappings proxy.
                def mappings(self):
                    return self

                #R020: Reuse-tagged scaffolding helper for fake row list.
                def all(self):
                    return []

            return R()

    class FakeClient:
        #R020: Plain reuse tag for shard-2 caching scaffolding coverage.
        def __init__(self, results):
            self._results = results

        #R020: Plain reuse tag for shard-2 caching scaffolding coverage.
        def search_candidates(self, query, limit=75):
            return self._results.pop(0) if self._results else []

        #R020: Plain reuse tag for shard-2 caching scaffolding coverage.
        def get_message(self, _mid, timeout_seconds=None):
            return {}

    #R020: Plain reuse tag for shard-2 caching scaffolding coverage.
    class FakeRanker:
        #R020: Reuse-tagged scaffolding helper for fake planned model.
        def planned_model_name(self):
            return "claude-sonnet-4-5"

        #R020: Plain reuse tag for shard-2 caching scaffolding coverage.
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
            #R020: Reuse-tagged scaffolding helper for context wrapper setup.
            def __init__(self, session):
                self.session = session

            #R020: Reuse-tagged scaffolding helper for context manager entry.
            def __enter__(self):
                return self.session

            #R020: Reuse-tagged scaffolding helper for context manager exit.
            def __exit__(self, *exc):
                return False

        #R020: Reuse-tagged scaffolding helper for fake repository constructor.
        def __init__(self, txn, last_summary, active):
            self.txn = txn
            self.last_summary = last_summary
            self.active = active
            self.created = 0

        #R020: Reuse-tagged scaffolding helper for fake session creation.
        def session(self):
            return FakeRepo.Ctx(_FakeSession())

        #R020: Reuse-tagged scaffolding helper for fake transaction loading.
        def load_transaction(self, session, transaction_id):
            return self.txn

        #R020: Reuse-tagged scaffolding helper for fake run summary lookup.
        def read_last_run_summary(self, session, transaction_id):
            return self.last_summary

        #R020: Reuse-tagged scaffolding helper for fake active match lookup.
        def read_active_match_summary(self, session, transaction_id):
            return self.active

        #R020: Reuse-tagged scaffolding helper for fake run creation.
        def create_run(self, **kwargs):
            self.created += 1
            return 201

        #R020: Reuse-tagged scaffolding helper for fake model update.
        def update_run_model_name(self, **kwargs):
            pass

        #R020: Reuse-tagged scaffolding helper for fake candidate insertion.
        def insert_candidates(self, **kwargs):
            pass

        #R020: Reuse-tagged scaffolding helper for fake AI result persistence.
        def persist_ai_result(self, **kwargs):
            return []

        #R020: Reuse-tagged scaffolding helper for fake failure marker.
        def mark_run_failed(self, *a, **_k):
            pass

    class _FakeSession:
        #R020: Reuse-tagged scaffolding helper for fake SQL execute behavior.
        def execute(self, *a, **_k):
            class R:
                #R020: Reuse-tagged scaffolding helper for fake mappings proxy.
                def mappings(self):
                    return self

                #R020: Reuse-tagged scaffolding helper for fake row list.
                def all(self):
                    return []

            return R()

    class FakeClient:
        #R020: Reuse-tagged scaffolding helper for fake client constructor.
        def __init__(self, results):
            self._results = results

        #R020: Reuse-tagged scaffolding helper for fake candidate search.
        def search_candidates(self, query, limit=75):
            return self._results.pop(0) if self._results else []

        #R020: Reuse-tagged scaffolding helper for fake message fetch.
        def get_message(self, _mid, timeout_seconds=None):
            return {}

    class FakeRanker:
        #R020: Reuse-tagged scaffolding helper for fake planned model.
        def planned_model_name(self):
            return "claude-sonnet-4-5"

        #R020: Reuse-tagged scaffolding helper for fake AI selection output.
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
