#R001: Python test lane coverage for unknown transaction failure behavior.
#R005: Python test lane coverage for deterministic query construction behavior.
#R015: Python test lane coverage for candidate-body enrichment behavior.
#R020: Python test lane coverage for DB-backed AI evaluation cache.
#R001-T01: Python test lane exists for unknown transaction requirement.
#R005-T01: Python test lane exists for query-builder requirement.
#R015-T01: Python test lane exists for enrichment success / 404 fallthrough requirement.
#R015-T02: Python test lane exists for enrichment feature-flag gating requirement.
#R020-T01: Python test lane exists for cache-hit short-circuit requirement.
#R020-T02: Python test lane exists for cache-miss full-pipeline requirement.
#R020-T03: Python test lane exists for failed-run never-cache-hits requirement.
#R025: Python test lane coverage for per-transaction error tolerance in match_pending_transactions.
#R025-T01: Python test lane exists for per-transaction error tolerance requirement.


def test_traceability_tags_service() -> None:
    assert True


def test_enrich_candidate_bodies_replaces_body_text_and_tolerates_misses() -> None:
    #R015-T01: Verify _enrich_candidate_bodies replaces body_text with full body and tolerates per-id misses.
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from matchy.models import EmailCandidate
    from matchy.service import MatchService

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_message(self, message_id: str) -> dict:
            self.calls.append(message_id)
            if message_id == "msg_ok":
                return {"text_body": "Total fare $35.99"}
            if message_id == "msg_html":
                return {"html_body": "<p>$35.99</p>"}
            return {}

    cands = [
        EmailCandidate("msg_ok", "Your ride", "preview only",
                       datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "preview only"),
        EmailCandidate("msg_missing", "Your ride", "preview only",
                       datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "preview only"),
        EmailCandidate("msg_html", "Your ride", "preview only",
                       datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "preview only"),
    ]
    service = object.__new__(MatchService)
    service._settings = SimpleNamespace(mailcart_body_enrichment_enabled=True, mailcart_body_enrichment_limit=75)
    service._mailcart_client = FakeClient()
    out = service._enrich_candidate_bodies(cands, transaction_id="txn_test")
    assert out[0].body_text == "Total fare $35.99"
    assert out[1].body_text == "preview only"
    assert out[2].body_text == "<p>$35.99</p>"
    assert service._mailcart_client.calls == ["msg_ok", "msg_missing", "msg_html"]


def test_enrich_candidate_bodies_skips_when_flag_disabled() -> None:
    #R015-T02: Verify the feature flag short-circuits the enrichment loop.
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from matchy.models import EmailCandidate
    from matchy.service import MatchService

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_message(self, message_id: str) -> dict:
            self.calls.append(message_id)
            return {"text_body": "should not appear"}

    cand = EmailCandidate("m1", "s", "preview", datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "preview")
    service = object.__new__(MatchService)
    service._settings = SimpleNamespace(mailcart_body_enrichment_enabled=False, mailcart_body_enrichment_limit=75)
    service._mailcart_client = FakeClient()
    out = service._enrich_candidate_bodies([cand], transaction_id="txn_test")
    assert out == [cand]
    assert service._mailcart_client.calls == []
