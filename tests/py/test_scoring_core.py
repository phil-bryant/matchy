#R010: Contract tests for normalized_text behavior.
#R015: Contract tests for token_overlap behavior.
#R020: Contract tests for amount_hint_score behavior.
#R025: Contract tests for sender_hint_score behavior.
#R030: Contract tests for compact_merchant_hint_score behavior.
#R035: Contract tests for time_proximity_score behavior.

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from matchy.models import EmailCandidate
from matchy import scoring_core

TZ = timezone.utc
BASE_TIME = datetime(2024, 6, 1, 12, 0, 0, tzinfo=TZ)


def email_candidate(subject: str = "", preview: str = "", body_text: str = "") -> EmailCandidate:
    return EmailCandidate("m1", subject, preview, BASE_TIME, "", body_text)


def test_normalized_text_lowercases_input() -> None:
    #R010-T01: Mixed case input becomes lowercase.
    assert scoring_core.normalized_text("HeLLo") == "hello"


def test_normalized_text_replaces_punctuation_with_spaces() -> None:
    #R010-T02: Punctuation becomes single-space separators.
    assert scoring_core.normalized_text("a,b;c") == "a b c"


def test_normalized_text_preserves_digits_and_spaces() -> None:
    #R010-T03: Alphanumeric tokens and spaces remain after normalization.
    assert scoring_core.normalized_text("x1 y2") == "x1 y2"


def test_normalized_text_strips_symbols_from_mixed_phrase() -> None:
    #R010-T04: Symbols in a mixed phrase normalize to spaced tokens.
    assert scoring_core.normalized_text("DoorDash order!") == "doordash order "


def test_token_overlap_empty_inputs_return_zero() -> None:
    #R015-T01: Missing token sets yield zero overlap.
    assert scoring_core.token_overlap("", "") == 0.0
    assert scoring_core.token_overlap("   ", "foo bar") == 0.0


def test_token_overlap_ignores_short_tokens() -> None:
    #R015-T02: Tokens with length two or less are excluded from overlap.
    assert scoring_core.token_overlap("ab ab", "abc abc") == 0.0


def test_token_overlap_excludes_length_two_tokens_on_left() -> None:
    #R015-T06: Two-character left tokens must not affect overlap scoring.
    assert scoring_core.token_overlap("xy abc", "abc") == 1.0


def test_token_overlap_excludes_length_two_tokens_on_right() -> None:
    #R015-T07: Two-character right tokens must not affect overlap scoring.
    assert scoring_core.token_overlap("abc", "xy abc") == 1.0


def test_token_overlap_exact_ratio_for_partial_match() -> None:
    #R015-T03: Overlap ratio uses intersection over max side length.
    assert scoring_core.token_overlap("foo bar baz", "foo bar qux") == pytest.approx(2 / 3)


def test_token_overlap_uses_larger_side_as_denominator() -> None:
    #R015-T04: Denominator is max token-set size, not min.
    assert scoring_core.token_overlap("alpha beta gamma", "alpha") == pytest.approx(1 / 3)


def test_token_overlap_one_side_without_long_tokens_returns_zero() -> None:
    #R015-T05: One side with no qualifying tokens yields zero overlap.
    assert scoring_core.token_overlap("foo bar", "xy") == 0.0


def test_amount_hint_score_matches_two_decimal_form() -> None:
    #R020-T01: Plain two-decimal amount text yields a full hint score.
    amount = Decimal("10.50")
    candidate = email_candidate(subject="payment 10.50 posted")
    assert scoring_core.amount_hint_score(amount, candidate) == 1.0


def test_amount_hint_score_matches_abs_decimal_form() -> None:
    #R020-T02: Absolute-value decimal hint text yields a full hint score.
    amount = Decimal("-10.50")
    candidate = email_candidate(preview="total 10.50 due")
    assert scoring_core.amount_hint_score(amount, candidate) == 1.0


def test_amount_hint_score_matches_dollar_form() -> None:
    #R020-T03: Dollar-prefixed absolute amount text yields a full hint score.
    amount = Decimal("-25.00")
    candidate = email_candidate(body_text="charged $25.00 today")
    assert scoring_core.amount_hint_score(amount, candidate) == 1.0


def test_amount_hint_score_matches_integer_form() -> None:
    #R020-T04: Whole-dollar amounts match integer-form tokens via cents normalization.
    amount = Decimal("42.00")
    candidate = email_candidate(subject="order 42 receipt")
    assert scoring_core.amount_hint_score(amount, candidate) == 1.0


def test_amount_hint_score_matches_thousands_separated_currency() -> None:
    #R020-T06: Thousands separators are parsed and matched at integer-cents precision.
    amount = Decimal("1234.56")
    candidate = email_candidate(body_text="Your total is $1,234.56")
    assert scoring_core.amount_hint_score(amount, candidate) == 1.0


def test_amount_hint_score_rejects_integer_token_for_non_whole_amount() -> None:
    #R020-T07: Integer tokens do not match non-whole amounts when cents differ.
    amount = Decimal("42.99")
    candidate = email_candidate(subject="order 42 receipt")
    assert scoring_core.amount_hint_score(amount, candidate) == 0.0


def test_amount_hint_score_returns_zero_without_amount_text() -> None:
    #R020-T05: Candidate text without amount hints yields zero.
    amount = Decimal("99.99")
    candidate = email_candidate(subject="newsletter", preview="unrelated")
    assert scoring_core.amount_hint_score(amount, candidate) == 0.0


def test_sender_hint_score_returns_one_for_shared_long_token() -> None:
    #R025-T01: Shared long tokens between txn and sender yield one.
    assert scoring_core.sender_hint_score("payment from acme retail", "acme@store.com acme") == 1.0


def test_sender_hint_score_returns_zero_without_overlap() -> None:
    #R025-T02: No shared long tokens yields zero.
    assert scoring_core.sender_hint_score("payment coffee shop", "books@store.com") == 0.0


def test_sender_hint_score_ignores_short_tokens_only() -> None:
    #R025-T03: Only short shared tokens do not produce a sender hint.
    assert scoring_core.sender_hint_score("ab cd ef", "ab gh") == 0.0


def test_sender_hint_score_returns_zero_for_empty_inputs() -> None:
    #R025-T04: Empty transaction or sender text yields zero.
    assert scoring_core.sender_hint_score("", "sender@x.com") == 0.0
    assert scoring_core.sender_hint_score("merchant payment", "") == 0.0


def test_sender_hint_score_requires_length_three_transaction_token() -> None:
    #R025-T05: Three-character transaction tokens count toward sender hints.
    assert scoring_core.sender_hint_score("pay ace billing", "ace@payments.com") == 1.0


def test_sender_hint_score_requires_length_three_sender_token() -> None:
    #R025-T06: Three-character sender tokens count toward sender hints.
    assert scoring_core.sender_hint_score("pay ace billing", "ace billing team") == 1.0


def test_compact_merchant_hint_score_returns_zero_for_empty_candidate() -> None:
    #R030-T01: Empty candidate text yields zero.
    assert scoring_core.compact_merchant_hint_score("payment widgets", "") == 0.0


def test_compact_merchant_hint_score_matches_embedded_long_token() -> None:
    #R030-T02: Long txn token embedded in compact candidate yields one.
    txn = "purchase widgets international"
    candidate = "Receipt: WIDGETSINTERNATIONAL-123"
    assert scoring_core.compact_merchant_hint_score(txn, candidate) == 1.0


def test_compact_merchant_hint_score_ignores_short_tokens() -> None:
    #R030-T03: Tokens shorter than six characters are ignored.
    assert scoring_core.compact_merchant_hint_score("buy alpha", "alphaonly") == 0.0


def test_compact_merchant_hint_score_ignores_digit_only_tokens() -> None:
    #R030-T04: Digit-only long tokens do not produce a compact merchant hint.
    assert scoring_core.compact_merchant_hint_score("ref 12345678", "12345678") == 0.0


def test_compact_merchant_hint_score_returns_zero_without_substring_match() -> None:
    #R030-T05: No embedded long token match yields zero.
    assert scoring_core.compact_merchant_hint_score("payment coffee", "tea-shop-receipt") == 0.0


def test_compact_merchant_hint_score_strips_punctuation_before_match() -> None:
    #R030-T06: Punctuation is removed from compact candidate text before matching.
    assert scoring_core.compact_merchant_hint_score("purchase foobar", "foo-bar") == 1.0


def test_compact_merchant_hint_score_matches_six_character_token() -> None:
    #R030-T07: Six-character transaction tokens are eligible for compact matching.
    assert scoring_core.compact_merchant_hint_score("buy widget", "widgetshop") == 1.0


def test_compact_merchant_hint_score_rejects_shorter_transaction_tokens() -> None:
    #R030-T08: Five-character transaction tokens do not produce compact hints.
    assert scoring_core.compact_merchant_hint_score("buy panel", "panelshop") == 0.0


@pytest.mark.parametrize(
    ("hours_delta", "expected"),
    [
        (0, 1.0),
        (6, 1.0),
        (6 + 1 / 3600, 0.85),
        (24, 0.85),
        (24 + 1 / 3600, 0.65),
        (72, 0.65),
        (72 + 1 / 3600, 0.3),
        (24 * 30, 0.3),
        (24 * 30 + 1 / 3600, 0.1),
    ],
)
def test_time_proximity_score_bucket_edges(hours_delta: float, expected: float) -> None:
    #R035-T01: Documented hour buckets return exact proximity scores.
    txn_time = BASE_TIME
    received_at = txn_time + timedelta(hours=hours_delta)
    assert scoring_core.time_proximity_score(txn_time, received_at) == expected


def test_time_proximity_score_uses_absolute_delta() -> None:
    #R035-T02: Earlier received_at still uses absolute hour distance.
    txn_time = BASE_TIME
    received_at = txn_time - timedelta(hours=3)
    assert scoring_core.time_proximity_score(txn_time, received_at) == 1.0


def test_relevance_tokens_keeps_long_tokens_and_repeats() -> None:
    #R040-T01: Long tokens are retained in order, including repeats, after normalization.
    assert scoring_core.relevance_tokens("Coffee, COFFEE!! be xy") == ["coffee", "coffee"]


def test_relevance_tokens_drops_short_tokens() -> None:
    #R040-T02: Tokens of length two or less are excluded, yielding an empty list when none qualify.
    assert scoring_core.relevance_tokens("a bb !! 999") == ["999"]
    assert scoring_core.relevance_tokens("a bb cc") == []


def test_document_frequencies_counts_documents_containing_token() -> None:
    #R041-T01: Document frequency counts documents (not occurrences) containing each long token.
    docs = ["coffee shop", "coffee beans", "tea time tea"]
    assert scoring_core.document_frequencies(docs) == {
        "coffee": 2,
        "shop": 1,
        "beans": 1,
        "tea": 1,
        "time": 1,
    }


def test_document_frequencies_empty_corpus_is_empty() -> None:
    #R041-T02: An empty corpus produces no document frequencies.
    assert scoring_core.document_frequencies([]) == {}


def test_inverse_document_frequency_known_values() -> None:
    #R042-T01: Smoothed BM25 idf matches the closed-form value for known corpus statistics.
    assert scoring_core.inverse_document_frequency(2, 1) == pytest.approx(math.log(2.0))
    assert scoring_core.inverse_document_frequency(10, 1) == pytest.approx(math.log(1.0 + 9.5 / 1.5))


def test_inverse_document_frequency_is_monotonic_in_rarity() -> None:
    #R042-T02: Rarer tokens (lower document frequency) receive strictly higher idf.
    assert scoring_core.inverse_document_frequency(10, 1) > scoring_core.inverse_document_frequency(10, 5)


def test_bm25_score_known_value() -> None:
    #R043-T01: BM25 relevance matches the closed-form value exercising tf, idf, k1, and b length norm.
    document = "coffee coffee beans extra terms here"
    score = scoring_core.bm25_score("coffee", document, corpus_size=2, document_frequency_map={"coffee": 1},
                                    average_document_length=3.0)
    assert score == pytest.approx(0.749348303, abs=1e-6)


def test_bm25_score_zero_when_query_token_absent() -> None:
    #R043-T02: A query token absent from the document contributes no relevance.
    assert scoring_core.bm25_score("zzzz", "coffee beans", 2, {"coffee": 1}, 3.0) == 0.0


def test_bm25_score_zero_for_empty_document_or_empty_corpus() -> None:
    #R043-T03: An empty document or empty corpus yields zero relevance.
    assert scoring_core.bm25_score("coffee", "", 2, {"coffee": 1}, 0.0) == 0.0
    assert scoring_core.bm25_score("coffee", "coffee beans", 0, {"coffee": 1}, 3.0) == 0.0


def test_bm25_score_length_normalization_uses_average_length() -> None:
    #R043-T04: A below-one average document length still drives the b length-normalization term.
    score = scoring_core.bm25_score("coffee", "coffee coffee", 2, {"coffee": 1}, 0.5)
    assert score == pytest.approx(0.504107040407233, abs=1e-9)


def test_bm25_score_zero_average_falls_back_to_neutral_length() -> None:
    #R043-T05: A zero average document length falls back to neutral normalization without dividing by zero.
    score = scoring_core.bm25_score("coffee", "coffee coffee", 2, {"coffee": 1}, 0.0)
    assert score == pytest.approx(0.749348303308049, abs=1e-9)


def test_bm25_score_single_token_document_and_single_document_corpus() -> None:
    #R043-T06: Documents of length one and single-document corpora still produce relevance.
    assert scoring_core.bm25_score("coffee", "coffee", 2, {"coffee": 1}, 1.0) == pytest.approx(0.6931471805599453, abs=1e-9)
    assert scoring_core.bm25_score("coffee", "coffee", 1, {"coffee": 1}, 1.0) == pytest.approx(0.28768207245178085, abs=1e-9)


def test_bm25_score_unknown_token_uses_zero_document_frequency() -> None:
    #R043-T07: A query token absent from the frequency map is treated as document frequency zero.
    score = scoring_core.bm25_score("rareword", "rareword beans", 5, {}, 2.0)
    assert score == pytest.approx(2.4849066497880004, abs=1e-9)


def test_bm25_score_accumulates_across_multiple_query_tokens() -> None:
    #R043-T08: Relevance sums the contribution of every distinct matching query token.
    score = scoring_core.bm25_score("coffee beans", "coffee beans extra", 2, {"coffee": 1, "beans": 1}, 3.0)
    assert score == pytest.approx(1.3862943611198906, abs=1e-9)


def test_bm25_relevance_requires_positive_saturation_boundary() -> None:
    #R044-T03: A saturation at or below the boundary still scales rather than collapsing to zero.
    assert scoring_core.bm25_relevance(4.0, saturation=0.5) == pytest.approx(0.8888888888888888, abs=1e-9)


def test_bm25_relevance_saturates_into_unit_interval() -> None:
    #R044-T01: Saturation maps raw BM25 scores into [0, 1) via score/(score+saturation).
    assert scoring_core.bm25_relevance(4.0) == pytest.approx(0.5)
    assert scoring_core.bm25_relevance(12.0, saturation=4.0) == pytest.approx(0.75)


def test_bm25_relevance_guards_nonpositive_inputs() -> None:
    #R044-T02: Non-positive scores or non-positive saturation collapse to zero relevance.
    assert scoring_core.bm25_relevance(0.0) == 0.0
    assert scoring_core.bm25_relevance(-1.0) == 0.0
    assert scoring_core.bm25_relevance(4.0, saturation=0.0) == 0.0


def test_subset_sum_reachable_finds_multi_item_total() -> None:
    #R045-T01: A subset summing exactly to the target is reachable.
    assert scoring_core.subset_sum_reachable([300, 700], 1000) is True


def test_subset_sum_reachable_returns_false_when_no_subset_matches() -> None:
    #R045-T02: No subset within bounds yields False, and overshooting sums are pruned.
    assert scoring_core.subset_sum_reachable([300, 800], 1000) is False
    assert scoring_core.subset_sum_reachable([], 1000) is False


def test_subset_sum_reachable_honors_tolerance_band() -> None:
    #R045-T03: Sums within the inclusive tolerance band match; values beyond it are excluded.
    assert scoring_core.subset_sum_reachable([300, 690], 1000, tolerance_cents=10) is True
    assert scoring_core.subset_sum_reachable([1010], 1000, tolerance_cents=10) is True
    assert scoring_core.subset_sum_reachable([1011], 1000, tolerance_cents=10) is False


def test_subset_sum_reachable_ignores_nonpositive_amounts_and_zero_target() -> None:
    #R045-T04: Non-positive amounts are ignored and a zero subset never satisfies a target.
    assert scoring_core.subset_sum_reachable([0, -5, 1000], 1000) is True
    assert scoring_core.subset_sum_reachable([500], 0) is False


def test_subset_sum_reachable_counts_single_cent_amounts() -> None:
    #R045-T05: A one-cent amount participates in subset sums (boundary above zero, not above one).
    assert scoring_core.subset_sum_reachable([1, 999], 1000) is True
    assert scoring_core.subset_sum_reachable([999], 1000) is False


def test_amount_reconciliation_score_matches_sum_of_line_items() -> None:
    #R046-T01: Reconciliation fires when the total equals a subset of smaller line items.
    candidate = email_candidate(subject="Item A $3.00", preview="Item B $7.00", body_text="thanks")
    assert scoring_core.amount_reconciliation_score(Decimal("10.00"), candidate) == 1.0


def test_amount_reconciliation_score_is_distinct_from_single_token_hint() -> None:
    #R046-T02: A single token equal to the total drives amount_hint but not reconciliation.
    candidate = email_candidate(subject="Total $10.00", preview="", body_text="")
    assert scoring_core.amount_hint_score(Decimal("10.00"), candidate) == 1.0
    assert scoring_core.amount_reconciliation_score(Decimal("10.00"), candidate) == 0.0


def test_amount_reconciliation_score_zero_without_reaching_subset() -> None:
    #R046-T03: Line items that cannot sum to the total yield zero, as does empty or zero-target input.
    partial = email_candidate(subject="$3.00", preview="$4.00", body_text="")
    assert scoring_core.amount_reconciliation_score(Decimal("10.00"), partial) == 0.0
    empty = email_candidate(subject="newsletter", preview="", body_text="")
    assert scoring_core.amount_reconciliation_score(Decimal("10.00"), empty) == 0.0
    assert scoring_core.amount_reconciliation_score(Decimal("0.00"), partial) == 0.0


def test_amount_reconciliation_score_includes_one_cent_line_items() -> None:
    #R046-T04: One-cent line items are retained (boundary strictly above zero) and can complete a subset.
    candidate = email_candidate(subject="rounding $0.01", preview="charge $9.99", body_text="")
    assert scoring_core.amount_reconciliation_score(Decimal("10.00"), candidate) == 1.0


def test_decimal_to_cents_uses_half_up_rounding_at_half_cent() -> None:
    #R020: Cents normalization rounds half-up (0.005 -> 1 cent), not banker's rounding.
    assert scoring_core._decimal_to_cents(Decimal("0.005")) == 1
    assert scoring_core._decimal_to_cents(Decimal("0.015")) == 2


def test_decimal_to_cents_scales_by_exactly_one_hundred() -> None:
    #R020: A whole-dollar value converts to exactly 100 cents per dollar.
    assert scoring_core._decimal_to_cents(Decimal("1.00")) == 100
    assert scoring_core._decimal_to_cents(Decimal("3.50")) == 350


def test_decimal_to_cents_returns_none_for_unquantizable_value() -> None:
    #R020: A value too large to quantize at cent precision resolves to None rather than a cents value.
    assert scoring_core._decimal_to_cents(Decimal("1E1000")) is None


def test_amount_hint_score_returns_zero_when_target_cents_unresolvable() -> None:
    #R020: An unresolvable target amount yields no hint (target cents is None -> zero, never a full match).
    candidate = email_candidate(subject="total 10.00 posted")
    assert scoring_core.amount_hint_score(Decimal("1E1000"), candidate) == 0.0


def test_amount_reconciliation_score_returns_zero_when_target_cents_unresolvable() -> None:
    #R046: An unresolvable target amount short-circuits reconciliation to zero without raising.
    candidate = email_candidate(subject="Item A $3.00", preview="Item B $7.00", body_text="")
    assert scoring_core.amount_reconciliation_score(Decimal("1E1000"), candidate) == 0.0


def test_subset_sum_reachable_default_tolerance_is_exact() -> None:
    #R045: The default tolerance is zero, so a near-miss subset does not satisfy the target.
    assert scoring_core.subset_sum_reachable([100], 99) is False
    assert scoring_core.subset_sum_reachable([100], 101) is False
    assert scoring_core.subset_sum_reachable([100], 100) is True


def test_bm25_relevance_default_saturation_is_four() -> None:
    #R044: The default saturation constant is 4.0, mapping a raw score of 4.0 to exactly 0.5.
    assert scoring_core.bm25_relevance(4.0) == pytest.approx(0.5)
    assert scoring_core.bm25_relevance(16.0) == pytest.approx(0.8)


def test_bm25_score_default_k1_and_b_constants() -> None:
    #R043: Default Okapi constants (k1=1.5, b=0.75) drive the closed-form relevance value (doc length != average).
    document = "coffee coffee beans extra terms here"
    score = scoring_core.bm25_score("coffee", document, corpus_size=2, document_frequency_map={"coffee": 1},
                                    average_document_length=3.0)
    assert score == pytest.approx(0.749348303308049, abs=1e-12)
