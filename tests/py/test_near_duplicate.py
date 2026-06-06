#R055: Python test lane coverage for near-duplicate SimHash collapsing.

from datetime import datetime, timezone
from types import SimpleNamespace

from matchy.models import EmailCandidate
from matchy.near_duplicate import NearDuplicateMixin, _hamming_distance, _simhash64


def test_simhash64_is_deterministic_and_sensitive_to_content() -> None:
    #R055-T01: SimHash is deterministic, equal for identical text, and differs for unrelated text.
    receipt = "Starbucks coffee order total confirmation receipt amount"
    assert _simhash64(receipt) == _simhash64(receipt)
    assert _simhash64("") == 0
    assert _hamming_distance(_simhash64(receipt), _simhash64("gardening newsletter weekly unrelated topics")) > 3


def test_hamming_distance_counts_differing_bits() -> None:
    #R055-T02: Hamming distance counts differing bits and is zero for equal fingerprints.
    assert _hamming_distance(0b1011, 0b0001) == 2
    assert _hamming_distance(42, 42) == 0


def test_collapse_near_duplicates_merges_clusters_and_preserves_distinct() -> None:
    #R055-T03: Identical bodies collapse to the first representative; distinct content survives.
    dt = datetime(2026, 5, 5, tzinfo=timezone.utc)
    body = "Starbucks coffee order total confirmation receipt amount due today"
    first = EmailCandidate("a", "Receipt", "", dt, "x@y", body)
    forwarded = EmailCandidate("b", "Receipt", "", dt, "x@y", body)
    unrelated = EmailCandidate("c", "News", "", dt, "z@w", "gardening newsletter weekly unrelated topics here")
    collapsed = NearDuplicateMixin._collapse_near_duplicates([first, forwarded, unrelated], max_distance=3)
    assert [candidate.message_id for candidate in collapsed] == ["a", "c"]


def test_collapse_near_duplicates_is_noop_when_disabled_or_trivial() -> None:
    #R055-T03: A non-positive threshold or a single-element list returns the input unchanged.
    dt = datetime(2026, 5, 5, tzinfo=timezone.utc)
    a = EmailCandidate("a", "Receipt", "", dt, "x@y", "same body text here")
    b = EmailCandidate("b", "Receipt", "", dt, "x@y", "same body text here")
    assert [c.message_id for c in NearDuplicateMixin._collapse_near_duplicates([a, b], max_distance=0)] == ["a", "b"]
    assert [c.message_id for c in NearDuplicateMixin._collapse_near_duplicates([a], max_distance=3)] == ["a"]


def test_near_duplicate_max_distance_defaults_off_and_validates() -> None:
    #R055-T04: Distance resolver defaults to disabled, honors positive values, and rejects invalid input.
    resolver = object.__new__(NearDuplicateMixin)
    resolver._settings = SimpleNamespace()
    assert resolver._near_duplicate_max_distance() == 0
    resolver._settings = SimpleNamespace(near_duplicate_max_hamming_distance=5)
    assert resolver._near_duplicate_max_distance() == 5
    resolver._settings = SimpleNamespace(near_duplicate_max_hamming_distance="bad")
    assert resolver._near_duplicate_max_distance() == 0
    resolver._settings = SimpleNamespace(near_duplicate_max_hamming_distance=-2)
    assert resolver._near_duplicate_max_distance() == 0
