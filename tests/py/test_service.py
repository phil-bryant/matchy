#R001: Python test lane coverage for unknown transaction errors.
#R005: Python test lane coverage for query builder normalization.
#R010: Python test lane coverage for pending matcher delegation.
#R015: Python test lane coverage for body enrichment behavior.
#R020: Python test lane coverage for cache hit/miss paths.
#R025: Python test lane coverage for batch failure tolerance.
#R030: Python test lane coverage for concurrent pending batch behavior.
#R040: Python test lane coverage for scoped search tiering and early-stop.
#R001-T01: Python test lane exists for unknown transaction requirement.
#R005-T01: Python test lane exists for query builder requirement.
#R010-T01: Python test lane exists for pending matcher requirement.
#R015-T01: Python test lane exists for body enrichment requirement.
#R015-T02: Python test lane exists for enrichment flag requirement.
#R020-T01: Python test lane exists for cache hit requirement.
#R020-T02: Python test lane exists for cache miss requirement.
#R020-T03: Python test lane exists for failed-run cache exclusion requirement.
#R025-T01: Python test lane exists for batch failure tolerance requirement.
#R030-T01: Python test lane exists for concurrent pending matcher requirement.
#R040-T01: Python test lane exists for early-stop on first successful tier.
#R040-T02: Python test lane exists for deterministic de-duplication order.

import logging
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from matchy.ai_ranker import PROMPT_VERSION
from matchy.cldr_cache import CldrCurrencyMatcher
from matchy.models import AiSelection, EmailCandidate, TransactionInput
from matchy.service import MatchService, _simhash64, _hamming_distance

_MAILCART_SCRIPTS = Path(__file__).resolve().parents[3] / "mailcart" / "scripts"
if str(_MAILCART_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_MAILCART_SCRIPTS))

import matchy_mailcart_api as mailcart_api  # noqa: E402


def test_service_raises_valueerror_for_unknown_transactions() -> None:
    #R001: Unknown transaction IDs raise ValueError.
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
    try:
        service.match_transaction("missing")
    except ValueError as exc:
        assert "Unknown transaction_id" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_service_query_builders_emit_scoped_tokens_with_date_bounds() -> None:
    #R005: Query helpers produce deterministic scoped query strings.
    service = object.__new__(MatchService)
    service._settings = SimpleNamespace(mailcart_search_date_window_days=45)
    terms = service._extract_search_terms("Payment #1234 at DoorDash.com", "DoorDash")
    scoped = service._build_scoped_queries(
        terms,
        datetime(2026, 5, 5, tzinfo=timezone.utc),
        include_date_window=True,
    )
    assert terms == ["doordash", "payment"]
    assert scoped == [
        "body:doordash from:2026-03-21 to:2026-06-19",
        "body:payment from:2026-03-21 to:2026-06-19",
    ]
    subject_scoped = service._build_scoped_queries(
        terms,
        datetime(2026, 5, 5, tzinfo=timezone.utc),
        fields=("subject",),
        include_date_window=False,
    )
    assert subject_scoped == ["subject:doordash", "subject:payment"]


def test_service_emits_mailcart_scoped_queries_that_pass_parser_contract() -> None:
    #R005: Every emitted query must satisfy mailcart's scoped-query parser contract.
    class FakeClient:
        def __init__(self):
            self.queries = []

        def search_candidates(self, query, limit=75):
            self.queries.append(query)
            return []

    service = object.__new__(MatchService)
    service._settings = SimpleNamespace(mailcart_search_date_window_days=45)
    service._mailcart_client = FakeClient()
    service._mailcart_failure_cooldown_seconds = 15
    service._mailcart_unavailable_until_monotonic = 0.0
    txn = TransactionInput(
        "txn_test",
        "acc",
        Decimal("76.08"),
        datetime(2026, 5, 24, tzinfo=timezone.utc),
        "DD *DOORDASH TACOMBI 855-431-0459",
        "DoorDash",
    )
    result = service._search_candidates(txn, transaction_id="txn_test")
    assert result == []
    assert service._mailcart_client.queries
    assert service._mailcart_client.queries[-1] == ""
    for query in service._mailcart_client.queries:
        mailcart_api._parse_scoped_query(query)


def test_service_enriches_candidate_bodies_with_full_mailcart_message_body_before_scoring() -> None:
    #R015: _enrich_candidate_bodies replaces body_text with full Mailcart body and tolerates per-id failures.
    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_message(self, message_id, timeout_seconds=None):
            self.calls.append(message_id)
            if message_id == "msg_ok":
                return {"text_body": "Total fare $35.99 thank you", "subject": "Receipt", "sender": "x@y"}
            if message_id == "msg_html":
                return {"html_body": "<p>$35.99</p>", "subject": "Receipt", "sender": "x@y"}
            return {}

    cands = [
        EmailCandidate(message_id="msg_ok", subject="Your ride", preview="preview only",
                       received_at=datetime(2026, 5, 5, tzinfo=timezone.utc), sender="x@y", body_text="preview only"),
        EmailCandidate(message_id="msg_missing", subject="Your ride", preview="preview only",
                       received_at=datetime(2026, 5, 5, tzinfo=timezone.utc), sender="x@y", body_text="preview only"),
        EmailCandidate(message_id="msg_html", subject="Your ride", preview="preview only",
                       received_at=datetime(2026, 5, 5, tzinfo=timezone.utc), sender="x@y", body_text="preview only"),
    ]
    service = object.__new__(MatchService)
    service._settings = SimpleNamespace(mailcart_body_enrichment_enabled=True, mailcart_body_enrichment_limit=75)
    service._mailcart_client = FakeClient()
    out = service._enrich_candidate_bodies(cands, transaction_id="txn_test")
    assert out[0].body_text == "Total fare $35.99 thank you"
    assert out[1].body_text == "preview only" and out[1].message_id == "msg_missing"
    assert out[2].body_text == "<p>$35.99</p>"
    assert service._mailcart_client.calls == ["msg_ok", "msg_missing", "msg_html"]


def test_service_enrichment_fetches_duplicate_message_ids_only_once() -> None:
    #R015: Duplicate candidate message_ids should not trigger duplicate get_message fetches.
    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_message(self, message_id, timeout_seconds=None):
            self.calls.append(message_id)
            return {"text_body": f"body-{message_id}"}

    dt = datetime(2026, 5, 5, tzinfo=timezone.utc)
    cands = [
        EmailCandidate(message_id="dup", subject="s", preview="p", received_at=dt, sender="x@y", body_text="preview"),
        EmailCandidate(message_id="dup", subject="s", preview="p", received_at=dt, sender="x@y", body_text="preview"),
        EmailCandidate(message_id="uniq", subject="s", preview="p", received_at=dt, sender="x@y", body_text="preview"),
    ]
    service = object.__new__(MatchService)
    service._settings = SimpleNamespace(
        mailcart_body_enrichment_enabled=True,
        mailcart_body_enrichment_limit=75,
        mailcart_body_enrichment_timeout_seconds=10,
        mailcart_body_enrichment_max_workers=4,
        mailcart_get_message_timeout_seconds=2,
    )
    service._mailcart_client = FakeClient()
    out = service._enrich_candidate_bodies(cands, transaction_id="txn_test")
    assert out[0].body_text == "body-dup"
    assert out[1].body_text == "body-dup"
    assert out[2].body_text == "body-uniq"
    assert service._mailcart_client.calls == ["dup", "uniq"]


def test_service_skips_body_enrichment_when_feature_flag_is_disabled() -> None:
    #R015: Enrichment is gated by mailcart_body_enrichment_enabled.
    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_message(self, message_id, timeout_seconds=None):
            self.calls.append(message_id)
            return {"text_body": "should-not-appear"}

    cand = EmailCandidate(message_id="m1", subject="s", preview="preview text",
                          received_at=datetime(2026, 5, 5, tzinfo=timezone.utc), sender="x@y", body_text="preview text")
    service = object.__new__(MatchService)
    service._settings = SimpleNamespace(mailcart_body_enrichment_enabled=False, mailcart_body_enrichment_limit=75)
    service._mailcart_client = FakeClient()
    out = service._enrich_candidate_bodies([cand], transaction_id="txn_test")
    assert out == [cand]
    assert service._mailcart_client.calls == []


def test_service_filters_enriched_candidates_without_standalone_cldr_currency_before_ai() -> None:
    #R050-T01: Currency filtering runs after full-body enrichment and before ranking/AI selection.
    class FakeRepo:
        class Ctx:
            def __enter__(self):
                return _FakeSession()
            def __exit__(self, *exc):
                return False
        def __init__(self, txn):
            self.txn = txn
            self.candidates_inserted = None
        def session(self):
            return FakeRepo.Ctx()
        def load_transaction(self, session, transaction_id):
            return self.txn
        def read_last_run_summary(self, session, transaction_id):
            return None
        def create_run(self, **kwargs):
            return 202
        def update_run_model_name(self, **kwargs):
            pass
        def insert_candidates(self, **kwargs):
            self.candidates_inserted = kwargs["candidates"]
        def persist_ai_result(self, **kwargs):
            return list(kwargs["ai_selection"].selected_message_ids)
        def mark_run_failed(self, *a, **k):
            pass

    class _FakeSession:
        def execute(self, *a, **k):
            class R:
                def mappings(self):
                    return self
                def all(self):
                    return []
            return R()

    class FakeClient:
        def search_candidates(self, query, limit=75):
            dt = datetime(2026, 5, 5, tzinfo=timezone.utc)
            return [
                EmailCandidate("good", "Receipt", "", dt, "x@y", ""),
                EmailCandidate("bad", "Receipt", "", dt, "x@y", ""),
                EmailCandidate("substring", "Receipt", "", dt, "x@y", ""),
            ]
        def get_message(self, message_id, timeout_seconds=None):
            bodies = {"good": "total $35.99", "bad": "total thirty five", "substring": "code xUSDx only"}
            return {"text_body": bodies[message_id]}

    class FakeRanker:
        def planned_model_name(self):
            return "claude-sonnet-4-5"
        def select(self, txn, ranked):
            assert [row.candidate.message_id for row in ranked] == ["good"]
            return AiSelection(["good"], 0.95, False, "currency scoped", "anthropic", "claude-sonnet-4-5")

    txn = TransactionInput("txn1", "acc", Decimal("35.99"), datetime(2026, 5, 5, tzinfo=timezone.utc), "LYFT", "")
    svc = object.__new__(MatchService)
    svc._settings = SimpleNamespace(
        mailcart_body_enrichment_enabled=True,
        mailcart_body_enrichment_limit=75,
        mailcart_body_enrichment_timeout_seconds=10,
        mailcart_body_enrichment_max_workers=4,
        mailcart_get_message_timeout_seconds=2,
        auto_confirm_threshold=0.9,
    )
    svc._repository = FakeRepo(txn)
    svc._mailcart_client = FakeClient()
    svc._ai_ranker = FakeRanker()
    svc._mailcart_failure_cooldown_seconds = 15
    svc._mailcart_unavailable_until_monotonic = 0.0
    svc._cldr_currency_matcher = CldrCurrencyMatcher(frozenset({"$", "USD"}))
    result = svc.match_transaction("txn1")
    assert result["selected_message_ids"] == ["good"]
    assert [row.candidate.message_id for row in svc._repository.candidates_inserted] == ["good"]


def test_service_currency_filter_leaves_candidates_unfiltered_when_matcher_is_empty() -> None:
    #R050-T02: Missing CLDR cache data produces an empty matcher and does not drop otherwise usable candidates.
    dt = datetime(2026, 5, 5, tzinfo=timezone.utc)
    candidates = [EmailCandidate("m1", "Receipt", "total", dt, "x@y", "body")]
    service = object.__new__(MatchService)
    service._cldr_currency_matcher = CldrCurrencyMatcher(frozenset())
    assert service._filter_currency_candidates(candidates) == candidates


def test_service_short_circuits_ai_call_when_candidate_set_is_unchanged_since_last_run() -> None:
    #R020: match_transaction returns skipped=True when (model, prompt, candidate set) match last run.
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

        def get_message(self, mid, timeout_seconds=None):
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

        def mark_run_failed(self, *a, **k):
            pass

    class _FakeSession:
        def execute(self, *a, **k):
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

        def get_message(self, mid, timeout_seconds=None):
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

        def mark_run_failed(self, *a, **k):
            pass

    class _FakeSession:
        def execute(self, *a, **k):
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

        def get_message(self, mid, timeout_seconds=None):
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

        def mark_run_failed(self, *a, **k):
            pass

    class _FakeSession:
        def execute(self, *a, **k):
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

        def get_message(self, mid, timeout_seconds=None):
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


def test_service_pending_matcher_tolerates_per_transaction_failures() -> None:
    #R025: One transaction's exception must not abort the whole batch.
    logging.getLogger("matchy.service").setLevel(logging.CRITICAL)

    class Repo:
        class Ctx:
            def __enter__(self):
                return object()

            def __exit__(self, *exc):
                return False

        def session(self):
            return Repo.Ctx()

        def list_pending_transaction_ids(self, session, limit=100, lookback_days=14):
            return ["txn_a", "txn_b", "txn_c"]

    service = object.__new__(MatchService)
    service._repository = Repo()

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
    class Repo:
        class Ctx:
            def __enter__(self):
                return object()

            def __exit__(self, exc_type, exc, tb):
                return False

        def session(self):
            return Repo.Ctx()

        def list_pending_transaction_ids(self, session, limit=100, lookback_days=14):
            return ["txn_1", "txn_2"]

    service = object.__new__(MatchService)
    service._repository = Repo()
    calls = []

    def fake_match_transaction(transaction_id, trigger_source="manual", force_rematch=False):
        calls.append((transaction_id, trigger_source))
        return {"transaction_id": transaction_id, "trigger_source": trigger_source}

    service.match_transaction = fake_match_transaction
    rows = service.match_pending_transactions(limit=9, lookback_days=2, trigger_source="auto")
    assert len(rows) == 2
    assert sorted(calls) == [("txn_1", "auto"), ("txn_2", "auto")]


def test_service_search_candidates_early_stops_on_first_success() -> None:
    #R040-T01: _search_candidates stops at the first tier that returns results.
    class Repo:
        class Ctx:
            def __enter__(self):
                return object()

            def __exit__(self, *exc):
                return False

        def session(self):
            return Repo.Ctx()

    class FakeClient:
        def __init__(self):
            self.queries: list[str] = []

        def search_candidates(self, query: str, limit: int = 75):
            self.queries.append(query)
            # Return a hit on any non-empty query to simulate first-tier success
            if query:
                return [EmailCandidate(message_id="m1", subject="s", preview="p", body_text="", received_at=datetime(2026, 5, 1, tzinfo=timezone.utc))]
            return []

    service = object.__new__(MatchService)
    service._repository = Repo()
    service._mailcart_client = FakeClient()
    service._settings = SimpleNamespace(mailcart_search_date_window_days=45)
    service._mailcart_failure_cooldown_seconds = 15
    service._mailcart_unavailable_until_monotonic = 0.0

    txn = TransactionInput(transaction_id="t", account_id="acc", amount=Decimal("10"), date=datetime(2026, 5, 1, tzinfo=timezone.utc), description="ACME", counterparty_name=None)
    results = service._search_candidates(txn, transaction_id="txn_r040")
    assert len(results) == 1
    assert results[0].message_id == "m1"
    # Early stop: last query should not be the final empty fallback
    assert service._mailcart_client.queries[-1] != ""


def test_service_search_candidates_dedupes_preserving_order() -> None:
    #R040-T02: _dedupe_candidates keeps first occurrence and preserves deterministic order.
    c1 = EmailCandidate(message_id="m1", subject="s", preview="p", body_text="", received_at=datetime(2026, 5, 1, tzinfo=timezone.utc))
    c2 = EmailCandidate(message_id="m2", subject="s", preview="p", body_text="", received_at=datetime(2026, 5, 1, tzinfo=timezone.utc))
    c3 = EmailCandidate(message_id="m1", subject="s", preview="p", body_text="", received_at=datetime(2026, 5, 1, tzinfo=timezone.utc))
    deduped = MatchService._dedupe_candidates([c1, c2, c3], limit=10)
    assert [d.message_id for d in deduped] == ["m1", "m2"]


def test_simhash64_is_deterministic_and_sensitive_to_content() -> None:
    #R055-T01: SimHash is deterministic, equal for identical text, and differs for unrelated text.
    receipt = "Starbucks coffee order total confirmation receipt amount"
    assert _simhash64(receipt) == _simhash64(receipt)
    assert _simhash64("") == 0
    assert _hamming_distance(_simhash64(receipt), _simhash64("gardening newsletter weekly unrelated topics")) > 3


def test_hamming_distance_counts_differing_bits() -> None:
    #R055-T02: Hamming distance counts differing bits and is zero for equal fingerprints.
    assert _hamming_distance(0b1011, 0b0001) == 2
    assert _hamming_distance(42, 42) == 0


def test_collapse_near_duplicates_merges_clusters_and_preserves_distinct() -> None:
    #R055-T03: Identical bodies collapse to the first representative; distinct content survives.
    dt = datetime(2026, 5, 5, tzinfo=timezone.utc)
    body = "Starbucks coffee order total confirmation receipt amount due today"
    first = EmailCandidate("a", "Receipt", "", dt, "x@y", body)
    forwarded = EmailCandidate("b", "Receipt", "", dt, "x@y", body)
    unrelated = EmailCandidate("c", "News", "", dt, "z@w", "gardening newsletter weekly unrelated topics here")
    collapsed = MatchService._collapse_near_duplicates([first, forwarded, unrelated], max_distance=3)
    assert [candidate.message_id for candidate in collapsed] == ["a", "c"]


def test_collapse_near_duplicates_is_noop_when_disabled_or_trivial() -> None:
    #R055-T03: A non-positive threshold or a single-element list returns the input unchanged.
    dt = datetime(2026, 5, 5, tzinfo=timezone.utc)
    a = EmailCandidate("a", "Receipt", "", dt, "x@y", "same body text here")
    b = EmailCandidate("b", "Receipt", "", dt, "x@y", "same body text here")
    assert [c.message_id for c in MatchService._collapse_near_duplicates([a, b], max_distance=0)] == ["a", "b"]
    assert [c.message_id for c in MatchService._collapse_near_duplicates([a], max_distance=3)] == ["a"]


def test_near_duplicate_max_distance_defaults_off_and_validates() -> None:
    #R055-T04: Distance resolver defaults to disabled, honors positive values, and rejects invalid input.
    service = object.__new__(MatchService)
    service._settings = SimpleNamespace()
    assert service._near_duplicate_max_distance() == 0
    service._settings = SimpleNamespace(near_duplicate_max_hamming_distance=5)
    assert service._near_duplicate_max_distance() == 5
    service._settings = SimpleNamespace(near_duplicate_max_hamming_distance="bad")
    assert service._near_duplicate_max_distance() == 0
    service._settings = SimpleNamespace(near_duplicate_max_hamming_distance=-2)
    assert service._near_duplicate_max_distance() == 0


def test_service_confirm_match_delegates_to_repository() -> None:
    #R045-T01: confirm_match calls deactivate + insert on repository (core behavior preventing state conflicts).
    calls = []

    class FakeRepo:
        class Ctx:
            def __enter__(self): return object()
            def __exit__(self, *a): return False
        def session(self): return FakeRepo.Ctx()
        def deactivate_active_match(self, s, txn): calls.append(("deact", txn))
        def insert_human_confirmed_match(self, s, txn, eml, note): calls.append(("insert", txn, eml, note))

    service = object.__new__(MatchService)
    service._repository = FakeRepo()
    service.confirm_match("t123", "e456", "note")
    assert calls == [("deact", "t123"), ("insert", "t123", "e456", "note")]
