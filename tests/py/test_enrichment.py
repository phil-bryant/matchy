#R015: Python test lane coverage for body enrichment behavior.
#R050: Python test lane coverage for CLDR currency candidate filtering.

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from matchy.cldr_cache import CldrCurrencyMatcher
from matchy.models import AiSelection, EmailCandidate, TransactionInput
from matchy.service import MatchService


def test_service_enriches_candidate_bodies_with_full_mailcart_message_body_before_scoring() -> None:
    #R015: _enrich_candidate_bodies replaces body_text with full Mailcart body and tolerates per-id failures.
    #R015-T01: Python test lane exists for body enrichment requirement.
    #R610-T01: Message payload fetch failures are tolerated while successful payloads are still applied.
    #R615-T01: Enrichment body extraction prefers available text/html/body fields in payload order.
    #R620-T01: Body enrichment rewrites configured candidate rows and leaves unresolved rows unchanged.
    class FakeClient:
        #R015: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.calls = []

        #R015: Test helper supports this requirement-focused scenario.
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
    #R605-T01: Enrichment deduplicates message ids before dispatching Mailcart fetches.
    class FakeClient:
        #R015: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.calls = []

        #R015: Test helper supports this requirement-focused scenario.
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
    #R015-T02: Python test lane exists for enrichment flag requirement.
    #R600-T01: Enrichment configuration short-circuits when the feature flag is disabled.
    class FakeClient:
        #R015: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.calls = []

        #R015: Test helper supports this requirement-focused scenario.
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
            #R050: Test helper supports this requirement-focused scenario.
            def __enter__(self):
                return _FakeSession()
            #R050: Test helper supports this requirement-focused scenario.
            def __exit__(self, *exc):
                return False
        #R050: Test helper supports this requirement-focused scenario.
        def __init__(self, txn):
            self.txn = txn
            self.candidates_inserted = None
        #R050: Test helper supports this requirement-focused scenario.
        def session(self):
            return FakeRepo.Ctx()
        #R050: Test helper supports this requirement-focused scenario.
        def load_transaction(self, session, transaction_id):
            return self.txn
        #R050: Test helper supports this requirement-focused scenario.
        def read_last_run_summary(self, session, transaction_id):
            return None
        #R050: Test helper supports this requirement-focused scenario.
        def create_run(self, **kwargs):
            return 202
        #R050: Test helper supports this requirement-focused scenario.
        def update_run_model_name(self, **kwargs):
            pass
        #R050: Test helper supports this requirement-focused scenario.
        def insert_candidates(self, **kwargs):
            self.candidates_inserted = kwargs["candidates"]
        #R050: Test helper supports this requirement-focused scenario.
        def persist_ai_result(self, **kwargs):
            return list(kwargs["ai_selection"].selected_message_ids)
        #R050: Test helper supports this requirement-focused scenario.
        def mark_run_failed(self, *a, **_k):
            pass

    class _FakeSession:
        #R050: Test helper supports this requirement-focused scenario.
        def execute(self, *a, **_k):
            class R:
                #R050: Test helper supports this requirement-focused scenario.
                def mappings(self):
                    return self
                #R050: Test helper supports this requirement-focused scenario.
                def all(self):
                    return []
            return R()

    class FakeClient:
        #R050: Test helper supports this requirement-focused scenario.
        def search_candidates(self, query, limit=75):
            dt = datetime(2026, 5, 5, tzinfo=timezone.utc)
            return [
                EmailCandidate("good", "Receipt", "", dt, "x@y", ""),
                EmailCandidate("bad", "Receipt", "", dt, "x@y", ""),
                EmailCandidate("substring", "Receipt", "", dt, "x@y", ""),
            ]
        #R050: Test helper supports this requirement-focused scenario.
        def get_message(self, message_id, timeout_seconds=None):
            bodies = {"good": "total $35.99", "bad": "total thirty five", "substring": "code xUSDx only"}
            return {"text_body": bodies[message_id]}

    class FakeRanker:
        #R050: Test helper supports this requirement-focused scenario.
        def planned_model_name(self):
            return "claude-sonnet-4-5"
        #R050: Test helper supports this requirement-focused scenario.
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
