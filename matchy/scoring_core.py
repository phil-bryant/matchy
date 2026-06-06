from __future__ import annotations

import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .models import EmailCandidate

#R005: Descending rank ordering is implemented in scoring.rank_candidates.
 #R001: Normalize text inputs to lowercase alphanumeric tokens for stable overlap scoring.
def normalized_text(value: str) -> str:
    lowered = value.lower()
    return re.sub(r"[^a-z0-9\s]", " ", lowered)


 #R010: Lowercase and strip non-alphanumeric characters before token overlap.
def token_overlap(left: str, right: str) -> float:
    left_tokens = {part for part in normalized_text(left).split() if len(part) > 2}
    right_tokens = {part for part in normalized_text(right).split() if len(part) > 2}
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return overlap / max(len(left_tokens), len(right_tokens))


 #R015: Token overlap uses long tokens only and returns a bounded ratio.
#R020: Amount hints compare exact integer-cents against money-like numeric tokens.
def amount_hint_score(amount: Decimal, candidate: EmailCandidate) -> float:
    text = f"{candidate.subject} {candidate.preview} {candidate.body_text}"
    target_cents = _decimal_to_cents(abs(amount))
    if target_cents is None:
        return 0.0
    for candidate_cents in _extract_money_cents(text):
        if candidate_cents == target_cents:
            return 1.0
    return 0.0


 #R760: Quantize Decimal values to cent precision using half-up rounding and return integer cents, or None on invalid input.
def _decimal_to_cents(value: Decimal) -> int | None:
    try:
        quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    return int((quantized * 100).to_integral_value(rounding=ROUND_HALF_UP))


 #R761: Extract money-like numeric tokens from text and normalize each parsed value into integer cents.
def _extract_money_cents(text: str) -> set[int]:
    cents: set[int] = set()
    pattern = re.compile(
        r"(?<!\d)(?:\$\s*)?([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)(?!\d)"
    )
    for match in pattern.finditer(text):
        raw = match.group(1).replace(",", "").strip()
        if not raw:
            continue
        try:
            numeric = Decimal(raw)
        except InvalidOperation:
            continue
        cents_value = _decimal_to_cents(abs(numeric))
        if cents_value is not None:
            cents.add(cents_value)
    return cents


 #R025: Sender hint is a binary long-token overlap signal.
def sender_hint_score(transaction_text: str, sender: str) -> float:
    normalized_txn = normalized_text(transaction_text)
    normalized_sender = normalized_text(sender)
    if not normalized_txn or not normalized_sender:
        return 0.0
    txn_tokens = {part for part in normalized_txn.split() if len(part) > 2}
    sender_tokens = {part for part in normalized_sender.split() if len(part) > 2}
    if not txn_tokens or not sender_tokens:
        return 0.0
    if txn_tokens & sender_tokens:
        return 1.0
    return 0.0


 #R030: Compact merchant hint matches long non-digit transaction tokens in candidate text.
def compact_merchant_hint_score(transaction_text: str, candidate_text: str) -> float:
    compact_candidate = re.sub(r"[^a-z0-9]", "", candidate_text.lower())
    if not compact_candidate:
        return 0.0
    normalized_txn = normalized_text(transaction_text)
    txn_tokens = [part for part in normalized_txn.split() if len(part) >= 6 and not part.isdigit()]
    for token in txn_tokens:
        if token in compact_candidate:
            return 1.0
    return 0.0


 #R035: Time proximity maps hour distance to documented score buckets.
def time_proximity_score(txn_time: datetime, received_at: datetime) -> float:
    delta_hours = abs((received_at - txn_time).total_seconds()) / 3600.0
    if delta_hours <= 6:
        return 1.0
    if delta_hours <= 24:
        return 0.85
    if delta_hours <= 72:
        return 0.65
    if delta_hours <= 24 * 30:
        return 0.3
    return 0.1


#R047: BM25 relevance and subset-sum reconciliation below are blended into the weighted ranking in scoring.rank_candidates.
#R040: Tokenize normalized text into long tokens (length greater than two) preserving repeats for term frequency.
def relevance_tokens(value: str) -> list[str]:
    tokens = [part for part in normalized_text(value).split() if len(part) > 2]
    return tokens


#R041: Count how many corpus documents contain each long token at least once (document frequency).
def document_frequencies(documents: list[str]) -> dict[str, int]:
    frequencies: dict[str, int] = {}
    for document in documents:
        for token in set(relevance_tokens(document)):
            frequencies[token] = frequencies.get(token, 0) + 1
    return frequencies


#R042: Smoothed BM25 inverse document frequency; rarer tokens across the corpus weigh more.
def inverse_document_frequency(corpus_size: int, document_frequency: int) -> float:
    numerator = corpus_size - document_frequency + 0.5
    denominator = document_frequency + 0.5
    value = math.log(1.0 + numerator / denominator)
    return value


#R043: Okapi BM25 relevance of a query against one document using corpus-level statistics.
def bm25_score(query: str, document: str, corpus_size: int, document_frequency_map: dict[str, int],
               average_document_length: float, k1: float = 1.5, b: float = 0.75) -> float:
    document_tokens = relevance_tokens(document)
    document_length = len(document_tokens)
    term_counts: dict[str, int] = {}
    for token in document_tokens:
        term_counts[token] = term_counts.get(token, 0) + 1
    length_norm = average_document_length if average_document_length > 0 else 1.0
    score = 0.0
    if document_length > 0 and corpus_size > 0:
        for query_token in set(relevance_tokens(query)):
            term_frequency = term_counts.get(query_token, 0)
            if term_frequency > 0:
                idf = inverse_document_frequency(corpus_size, document_frequency_map.get(query_token, 0))
                denominator = term_frequency + k1 * (1.0 - b + b * (document_length / length_norm))
                score += idf * (term_frequency * (k1 + 1.0)) / denominator
    return score


#R044: Saturate a non-negative BM25 score into the unit interval so it can blend with bounded signals.
def bm25_relevance(score: float, saturation: float = 4.0) -> float:
    normalized = 0.0
    if score > 0.0 and saturation > 0.0:
        normalized = score / (score + saturation)
    return normalized


#R045: Subset-sum reachability: does any non-empty subset of positive integer-cent amounts land within
#R045: tolerance of the target? Pseudo-polynomial DP pruned by the upper bound keeps the state set small.
def subset_sum_reachable(amounts_cents: list[int], target_cents: int, tolerance_cents: int = 0) -> bool:
    upper_bound = target_cents + tolerance_cents
    lower_bound = target_cents - tolerance_cents
    reachable = {0}
    for amount in amounts_cents:
        if amount > 0:
            additions = {partial + amount for partial in reachable if partial + amount <= upper_bound}
            reachable = reachable | additions
    found = False
    for total in reachable:
        if total != 0 and lower_bound <= total <= upper_bound:
            found = True
    return found


#R046: Reconciliation signal: fire when the transaction total equals a subset of smaller candidate
#R046: line-item amounts. Amounts at or above the target are excluded so any reaching subset needs two
#R046: or more items, making this distinct from the single-token amount_hint_score. Capped term count
#R046: bounds the DP state space for adversarial inputs.
def amount_reconciliation_score(amount: Decimal, candidate: EmailCandidate, max_terms: int = 12) -> float:
    text = f"{candidate.subject} {candidate.preview} {candidate.body_text}"
    target_cents = _decimal_to_cents(abs(amount))
    score = 0.0
    if target_cents is not None and target_cents > 0:
        line_items = sorted(cents for cents in _extract_money_cents(text) if 0 < cents < target_cents)
        if subset_sum_reachable(line_items[:max_terms], target_cents):
            score = 1.0
    return score
