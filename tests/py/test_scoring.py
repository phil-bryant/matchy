#R001: Python test lane coverage for text normalization scoring behavior.
#R005: Python test lane coverage for descending ranking behavior.

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from matchy.models import EmailCandidate, TransactionInput
from matchy.scoring import rank_candidates


def test_scoring_normalization_handles_punctuation_differences() -> None:
    #R001: Token overlap works after punctuation normalization.
    #R001-T01: Python test lane exists for normalization requirement.
    txn = TransactionInput("tx", "a", Decimal("10.00"), datetime.now(timezone.utc), "DoorDash order!", "")
    cand = EmailCandidate("m1", "Doordash-order receipt", "", datetime.now(timezone.utc))
    ranked = rank_candidates(txn, [cand], set())
    assert ranked[0].reasons["description_overlap"] > 0


def test_scoring_returns_candidates_sorted_by_descending_score() -> None:
    #R005: Ranking output is sorted highest score first.
    #R005-T01: Python test lane exists for descending-order requirement.
    now = datetime.now(timezone.utc)
    txn = TransactionInput("tx", "a", Decimal("10.00"), now, "Coffee shop", "Coffee")
    hi = EmailCandidate("m1", "Coffee receipt", "$10.00", now)
    lo = EmailCandidate("m2", "Random newsletter", "", now - timedelta(days=30))
    ranked = rank_candidates(txn, [lo, hi], set())
    assert ranked[0].candidate.message_id == "m1"
    assert ranked[0].score >= ranked[1].score


def test_rank_candidates_exposes_blended_reason_keys() -> None:
    #R047-T01: Ranked candidates always expose the BM25 and reconciliation reason keys, both bounded.
    now = datetime.now(timezone.utc)
    txn = TransactionInput("tx", "a", Decimal("10.00"), now, "Coffee shop", "Coffee")
    cand = EmailCandidate("m1", "Coffee receipt", "$3.00 plus $7.00", now)
    ranked = rank_candidates(txn, [cand], set())
    reasons = ranked[0].reasons
    assert "bm25_relevance" in reasons and 0.0 <= reasons["bm25_relevance"] <= 1.0
    assert "amount_reconciliation" in reasons and 0.0 <= reasons["amount_reconciliation"] <= 1.0


def test_rank_candidates_bm25_prefers_distinctive_token_overlap() -> None:
    #R047-T02: A candidate sharing the distinctive merchant token outranks an unrelated candidate.
    now = datetime.now(timezone.utc)
    txn = TransactionInput("tx", "a", Decimal("10.00"), now, "Bluebottle Coffee", "Bluebottle")
    match = EmailCandidate("m1", "Bluebottle order confirmation", "thanks", now)
    other = EmailCandidate("m2", "Generic monthly newsletter", "updates", now)
    ranked = rank_candidates(txn, [other, match], set())
    assert ranked[0].candidate.message_id == "m1"
    assert ranked[0].reasons["bm25_relevance"] > ranked[1].reasons["bm25_relevance"]


def test_rank_candidates_reconciliation_signals_multi_item_receipt() -> None:
    #R047-T03: Subset-sum reconciliation lifts a receipt whose line items total the transaction amount.
    now = datetime.now(timezone.utc)
    txn = TransactionInput("tx", "a", Decimal("10.00"), now, "Grocery", "Grocery")
    receipt = EmailCandidate("m1", "Grocery receipt", "milk $3.00 bread $7.00", now)
    ranked = rank_candidates(txn, [receipt], set())
    assert ranked[0].reasons["amount_reconciliation"] == 1.0
