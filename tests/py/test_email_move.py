#R060: Python test lane coverage for post-selection Mailcart email move.

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from matchy.cldr_cache import CldrCurrencyMatcher
from matchy.models import AiSelection, EmailCandidate, TransactionInput
from matchy.service import MatchService


def test_service_match_transaction_moves_selected_messages_when_email_move_is_enabled() -> None:
    #R060-T01: Successful AI-selected ids are moved to Mailcart's matchy folder when move flag is enabled.
    class FakeSession:
        #R060: Test helper supports this requirement-focused scenario.
        def execute(self, *a, **_k):
            class R:
                #R060: Test helper supports this requirement-focused scenario.
                def mappings(self):
                    return self
                #R060: Test helper supports this requirement-focused scenario.
                def all(self):
                    return []
            return R()

    class FakeRepo:
        class Ctx:
            #R060: Test helper supports this requirement-focused scenario.
            def __init__(self, session):
                self._session = session
            #R060: Test helper supports this requirement-focused scenario.
            def __enter__(self):
                return self._session
            #R060: Test helper supports this requirement-focused scenario.
            def __exit__(self, *exc):
                return False
        #R060: Test helper supports this requirement-focused scenario.
        def __init__(self, txn):
            self._txn = txn
            self._session = FakeSession()
        #R060: Test helper supports this requirement-focused scenario.
        def session(self):
            return FakeRepo.Ctx(self._session)
        #R060: Test helper supports this requirement-focused scenario.
        def load_transaction(self, _session, _transaction_id):
            return self._txn
        #R060: Test helper supports this requirement-focused scenario.
        def read_last_run_summary(self, _session, _transaction_id):
            return None
        #R060: Test helper supports this requirement-focused scenario.
        def create_run(self, **_kwargs):
            return 501
        #R060: Test helper supports this requirement-focused scenario.
        def update_run_model_name(self, **_kwargs):
            pass
        #R060: Test helper supports this requirement-focused scenario.
        def insert_candidates(self, **_kwargs):
            pass
        #R060: Test helper supports this requirement-focused scenario.
        def persist_ai_result(self, **_kwargs):
            return ["msg_move"]
        #R060: Test helper supports this requirement-focused scenario.
        def mark_run_failed(self, *_args, **_kwargs):
            pass

    class FakeMailcartClient:
        #R060: Test helper supports this requirement-focused scenario.
        def __init__(self):
            self.moved = []
        #R060: Test helper supports this requirement-focused scenario.
        def search_candidates(self, query, limit=75):
            return [
                EmailCandidate(
                    message_id="msg_move",
                    subject="Receipt",
                    preview="p",
                    received_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
                    sender="x@y",
                    body_text="body",
                )
            ]
        #R060: Test helper supports this requirement-focused scenario.
        def get_message(self, _message_id, timeout_seconds=None):
            return {}
        #R060: Test helper supports this requirement-focused scenario.
        def move_to_matchy(self, message_id):
            self.moved.append(message_id)
            return True

    class FakeRanker:
        #R060: Test helper supports this requirement-focused scenario.
        def planned_model_name(self):
            return "claude-sonnet-4-5"
        #R060: Test helper supports this requirement-focused scenario.
        def select(self, _txn, _ranked):
            return AiSelection(
                selected_message_ids=["msg_move"],
                confidence=0.95,
                uncertain=False,
                rationale="ok",
                backend="anthropic",
                model_name="claude-sonnet-4-5",
            )

    txn = TransactionInput("txn_move", "acc", Decimal("11.00"), datetime(2026, 5, 5, tzinfo=timezone.utc), "ACME", "ACME")
    service = object.__new__(MatchService)
    service._settings = SimpleNamespace(
        auto_confirm_threshold=0.9,
        mailcart_body_enrichment_enabled=False,
        near_duplicate_max_hamming_distance=0,
        email_move_enabled=True,
        write_enabled=True,
    )
    service._repository = FakeRepo(txn)
    service._mailcart_client = FakeMailcartClient()
    service._ai_ranker = FakeRanker()
    service._mailcart_failure_cooldown_seconds = 15
    service._mailcart_unavailable_until_monotonic = 0.0
    service._cldr_currency_matcher = CldrCurrencyMatcher(frozenset())
    service.match_transaction("txn_move")
    assert service._mailcart_client.moved == ["msg_move"]
