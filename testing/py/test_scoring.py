#R001: Python test lane coverage for text normalization scoring behavior.
#R005: Python test lane coverage for descending ranking behavior.
#R001-T01: Python test lane exists for normalization requirement.
#R005-T01: Python test lane exists for descending-order requirement.

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from matchy.models import EmailCandidate, TransactionInput
from matchy.scoring import rank_candidates


def test_scoring_normalization_handles_punctuation_differences() -> None:
    #R001: Token overlap works after punctuation normalization.
    txn = TransactionInput("tx", "a", Decimal("10.00"), datetime.now(timezone.utc), "DoorDash order!", "")
    cand = EmailCandidate("m1", "Doordash-order receipt", "", datetime.now(timezone.utc))
    ranked = rank_candidates(txn, [cand], set())
    assert ranked[0].reasons["description_overlap"] > 0


def test_scoring_returns_candidates_sorted_by_descending_score() -> None:
    #R005: Ranking output is sorted highest score first.
    now = datetime.now(timezone.utc)
    txn = TransactionInput("tx", "a", Decimal("10.00"), now, "Coffee shop", "Coffee")
    hi = EmailCandidate("m1", "Coffee receipt", "$10.00", now)
    lo = EmailCandidate("m2", "Random newsletter", "", now - timedelta(days=30))
    ranked = rank_candidates(txn, [lo, hi], set())
    assert ranked[0].candidate.message_id == "m1"
    assert ranked[0].score >= ranked[1].score
