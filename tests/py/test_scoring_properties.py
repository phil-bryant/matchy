#R001: Property tests ensure scoring invariants hold under randomized inputs.
#R005: Property tests ensure rank_candidates output stays sorted by descending score.
#R010: Property tests use Hypothesis strategies with lane-controlled example budgets.
#R015: Property tests cover scoring_core helpers and rank_candidates integration paths.
#R030: Semantic property tests pin scoring buckets and normalization charset rules.

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st

from matchy.models import EmailCandidate, TransactionInput
from matchy.scoring import rank_candidates
from matchy import scoring_core

TZ = timezone.utc
BASE_TIME = datetime(2024, 6, 1, 12, 0, 0, tzinfo=TZ)
REASON_KEYS = frozenset(
    {
        "merchant_overlap",
        "description_overlap",
        "amount_hint",
        "compact_merchant_hint",
        "sender_hint",
        "time_proximity",
        "bm25_relevance",
        "amount_reconciliation",
        "unmatched_email_priority",
    }
)


#R010: Test helper supports this requirement-focused scenario.
def fuzz_settings() -> hypothesis_settings:
    max_examples = int(os.environ.get("HYPOTHESIS_MAX_EXAMPLES", "50"))
    deadline_ms = int(os.environ.get("HYPOTHESIS_DEADLINE", "200"))
    return hypothesis_settings(max_examples=max_examples, deadline=deadline_ms)


@st.composite
#R001: Test helper supports this requirement-focused scenario.
def fuzz_text(draw: st.DrawFn) -> str:
    return draw(
        st.one_of(
            st.just(""),
            st.text(min_size=1, max_size=8, alphabet="Aa0! \n\t"),
            st.text(alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z", "S")), max_size=120),
        )
    )


@st.composite
#R001: Test helper supports this requirement-focused scenario.
def fuzz_datetime(draw: st.DrawFn) -> datetime:
    base = datetime(2018, 1, 1, tzinfo=TZ)
    offset_hours = draw(st.integers(min_value=-24 * 400, max_value=24 * 400))
    return base + timedelta(hours=offset_hours)


@st.composite
#R001: Test helper supports this requirement-focused scenario.
def fuzz_amount(draw: st.DrawFn) -> Decimal:
    raw = draw(
        st.decimals(
            min_value=-999999,
            max_value=999999,
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    return Decimal(str(raw))


@st.composite
#R001: Test helper supports this requirement-focused scenario.
def email_candidate(draw: st.DrawFn, index: int) -> EmailCandidate:
    return EmailCandidate(
        f"m{index}",
        draw(fuzz_text()),
        draw(fuzz_text()),
        draw(fuzz_datetime()),
        draw(fuzz_text()),
        draw(fuzz_text()),
    )


@st.composite
#R001: Test helper supports this requirement-focused scenario.
def email_candidates(draw: st.DrawFn) -> list[EmailCandidate]:
    count = draw(st.integers(min_value=0, max_value=8))
    return [draw(email_candidate(index)) for index in range(count)]


@st.composite
#R001: Test helper supports this requirement-focused scenario.
def transaction_input(draw: st.DrawFn) -> TransactionInput:
    return TransactionInput(
        draw(st.text(min_size=1, max_size=16, alphabet="abcdefghijklmnopqrstuvwxyz0123456789")),
        draw(st.text(min_size=1, max_size=16, alphabet="abcdefghijklmnopqrstuvwxyz0123456789")),
        draw(fuzz_amount()),
        draw(fuzz_datetime()),
        draw(fuzz_text()),
        draw(fuzz_text()),
    )


@fuzz_settings()
@given(left=fuzz_text(), right=fuzz_text())
def test_normalized_text_is_lowercase_token_safe(left: str, right: str) -> None:
    #R001: Normalization never raises and only emits lowercase alnum tokens/spaces.
    for value in (left, right):
        normalized = scoring_core.normalized_text(value)
        assert isinstance(normalized, str)
        assert normalized == normalized.lower()
        assert all(part.isalnum() or part == "" for part in normalized.split())


@fuzz_settings()
@given(value=fuzz_text())
def test_normalized_text_strips_non_alnum_to_spaces(value: str) -> None:
    #R030: Normalized output keeps only lowercase alnum and whitespace characters.
    normalized = scoring_core.normalized_text(value)
    assert normalized == normalized.lower()
    assert all(character.isalnum() or character.isspace() for character in normalized)


@fuzz_settings()
@given(hours_delta=st.floats(min_value=0.0, max_value=24 * 365, allow_nan=False, allow_infinity=False))
def test_time_proximity_matches_bucket_for_known_deltas(hours_delta: float) -> None:
    #R030: Documented hour buckets return exact proximity scores across the full delta domain.
    received_at = BASE_TIME + timedelta(hours=hours_delta)
    effective_hours = abs((received_at - BASE_TIME).total_seconds()) / 3600.0
    expected = 0.1
    if effective_hours <= 6:
        expected = 1.0
    elif effective_hours <= 24:
        expected = 0.85
    elif effective_hours <= 72:
        expected = 0.65
    elif effective_hours <= 24 * 30:
        expected = 0.3
    assert scoring_core.time_proximity_score(BASE_TIME, received_at) == expected


@fuzz_settings()
@given(left=fuzz_text(), right=fuzz_text())
def test_token_overlap_bounded(left: str, right: str) -> None:
    #R001: Token overlap stays within [0, 1].
    overlap = scoring_core.token_overlap(left, right)
    assert 0.0 <= overlap <= 1.0


@fuzz_settings()
@given(amount=fuzz_amount(), candidate=email_candidate(0))
def test_amount_hint_score_bounded(amount: Decimal, candidate: EmailCandidate) -> None:
    #R001: Amount hint score stays within [0, 1].
    score = scoring_core.amount_hint_score(amount, candidate)
    assert 0.0 <= score <= 1.0


@fuzz_settings()
@given(transaction_text=fuzz_text(), sender=fuzz_text())
def test_sender_hint_score_bounded(transaction_text: str, sender: str) -> None:
    #R001: Sender hint score stays within [0, 1].
    score = scoring_core.sender_hint_score(transaction_text, sender)
    assert 0.0 <= score <= 1.0


@fuzz_settings()
@given(transaction_text=fuzz_text(), candidate_text=fuzz_text())
def test_compact_merchant_hint_score_bounded(transaction_text: str, candidate_text: str) -> None:
    #R001: Compact merchant hint score stays within [0, 1].
    score = scoring_core.compact_merchant_hint_score(transaction_text, candidate_text)
    assert 0.0 <= score <= 1.0


@fuzz_settings()
@given(txn_time=fuzz_datetime(), received_at=fuzz_datetime())
def test_time_proximity_score_bounded(txn_time: datetime, received_at: datetime) -> None:
    #R001: Time proximity score stays within documented bucket range.
    score = scoring_core.time_proximity_score(txn_time, received_at)
    assert 0.1 <= score <= 1.0


@fuzz_settings()
@given(transaction=transaction_input(), candidates=email_candidates(), matched=st.sets(st.text(min_size=1, max_size=8)))
def test_rank_candidates_never_raises_and_scores_bounded(
    transaction: TransactionInput, candidates: list[EmailCandidate], matched: set[str]
) -> None:
    #R001: Randomized inputs must not crash and scores stay in [0, 1].
    ranked = rank_candidates(transaction, candidates, matched)
    assert len(ranked) == len(candidates)
    for row in ranked:
        assert 0.0 <= row.score <= 1.0


@fuzz_settings()
@given(transaction=transaction_input(), candidates=email_candidates(), matched=st.sets(st.text(min_size=1, max_size=8)))
def test_rank_candidates_sorted_descending(
    transaction: TransactionInput, candidates: list[EmailCandidate], matched: set[str]
) -> None:
    #R005: Output order is non-increasing by score.
    ranked = rank_candidates(transaction, candidates, matched)
    scores = [row.score for row in ranked]
    assert scores == sorted(scores, reverse=True)


@fuzz_settings()
@given(transaction=transaction_input(), matched=st.sets(st.text(min_size=1, max_size=8)))
def test_rank_candidates_empty_list(transaction: TransactionInput, matched: set[str]) -> None:
    #R001: Empty candidate input returns empty output.
    assert rank_candidates(transaction, [], matched) == []


@fuzz_settings()
@given(transaction=transaction_input(), candidates=email_candidates(), matched=st.sets(st.text(min_size=1, max_size=8)))
def test_rank_candidates_preserves_message_ids(
    transaction: TransactionInput, candidates: list[EmailCandidate], matched: set[str]
) -> None:
    #R015: Every input candidate appears exactly once in ranked output.
    ranked = rank_candidates(transaction, candidates, matched)
    input_ids = {candidate.message_id for candidate in candidates}
    output_ids = [row.candidate.message_id for row in ranked]
    assert len(output_ids) == len(set(output_ids))
    assert set(output_ids) == input_ids


@fuzz_settings()
@given(transaction=transaction_input(), candidates=email_candidates(), matched=st.sets(st.text(min_size=1, max_size=8)))
def test_rank_candidates_reason_keys_stable(
    transaction: TransactionInput, candidates: list[EmailCandidate], matched: set[str]
) -> None:
    #R015: Reason payloads always expose the full scoring feature set.
    ranked = rank_candidates(transaction, candidates, matched)
    for row in ranked:
        assert set(row.reasons.keys()) == REASON_KEYS


@fuzz_settings()
@given(transaction=transaction_input(), candidates=email_candidates())
def test_rank_candidates_matched_ids_disable_unmatched_bonus(
    transaction: TransactionInput, candidates: list[EmailCandidate]
) -> None:
    #R015: Already matched candidates never receive unmatched priority bonus.
    matched = {candidate.message_id for candidate in candidates}
    ranked = rank_candidates(transaction, candidates, matched)
    for row in ranked:
        assert row.reasons["unmatched_email_priority"] is False


@fuzz_settings()
@given(transaction=transaction_input(), candidates=email_candidates(), matched=st.sets(st.text(min_size=1, max_size=8)))
def test_rank_candidates_is_deterministic(
    transaction: TransactionInput, candidates: list[EmailCandidate], matched: set[str]
) -> None:
    #R015: Repeated ranking with identical inputs yields identical scores.
    first = rank_candidates(transaction, candidates, matched)
    second = rank_candidates(transaction, candidates, matched)
    assert [row.score for row in first] == [row.score for row in second]
    assert [row.candidate.message_id for row in first] == [row.candidate.message_id for row in second]
