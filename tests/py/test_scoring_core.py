#R010: Contract tests for normalized_text behavior.
#R015: Contract tests for token_overlap behavior.
#R020: Contract tests for amount_hint_score behavior.
#R025: Contract tests for sender_hint_score behavior.
#R030: Contract tests for compact_merchant_hint_score behavior.
#R035: Contract tests for time_proximity_score behavior.

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
    #R020-T04: Integer absolute amount text yields a full hint score.
    amount = Decimal("42.99")
    candidate = email_candidate(subject="order 42 receipt")
    assert scoring_core.amount_hint_score(amount, candidate) == 1.0


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
