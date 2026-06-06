#R005: Python test lane coverage for query builder normalization.
#R040: Python test lane coverage for scoped search tiering and early-stop.

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from matchy.models import EmailCandidate, TransactionInput
from matchy.service import MatchService

_MAILCART_SCRIPTS = Path(__file__).resolve().parents[3] / "mailcart" / "scripts"
if str(_MAILCART_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_MAILCART_SCRIPTS))

import matchy_mailcart_api as mailcart_api  # noqa: E402


def test_service_query_builders_emit_scoped_tokens_with_date_bounds() -> None:
    #R005: Query helpers produce deterministic scoped query strings.
    #R005-T01: Python test lane exists for query builder requirement.
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
        #R005: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.queries = []

        #R005: Test helper supports this requirement-focused scenario.
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


def test_service_search_candidates_early_stops_on_first_success() -> None:
    #R040-T01: _search_candidates stops at the first tier that returns results.
    class Repo:
        class Ctx:
            #R040: Test helper supports this requirement-focused scenario.
            def __enter__(self):
                return object()

            #R040: Test helper supports this requirement-focused scenario.
            def __exit__(self, *exc):
                return False

        #R040: Test helper supports this requirement-focused scenario.
        def session(self):
            return Repo.Ctx()

    class FakeClient:
        #R040: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.queries: list[str] = []

        #R040: Test helper supports this requirement-focused scenario.
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
