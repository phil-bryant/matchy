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
        def execute(self, *a, **_k):
            class R:
                def mappings(self):
                    return self
                def all(self):
                    return []
            return R()

    class FakeRepo:
        class Ctx:
            def __init__(self, session):
                self._session = session
            def __enter__(self):
                return self._session
            def __exit__(self, *exc):
                return False
        def __init__(self, txn):
            self._txn = txn
            self._session = FakeSession()
        def session(self):
            return FakeRepo.Ctx(self._session)
        def load_transaction(self, _session, _transaction_id):
            return self._txn
        def read_last_run_summary(self, _session, _transaction_id):
            return None
        def create_run(self, **_kwargs):
            return 501
        def update_run_model_name(self, **_kwargs):
            pass
        def insert_candidates(self, **_kwargs):
            pass
        def persist_ai_result(self, **_kwargs):
            return ["msg_move"]
        def mark_run_failed(self, *_args, **_kwargs):
            pass

    class FakeMailcartClient:
        def __init__(self):
            self.moved = []
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
        def get_message(self, _message_id, timeout_seconds=None):
            return {}
        def move_to_matchy(self, message_id):
            self.moved.append(message_id)
            return True

    class FakeRanker:
        def planned_model_name(self):
            return "claude-sonnet-4-5"
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
