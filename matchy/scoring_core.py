from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

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
 #R020: Amount hints match common decimal, absolute, dollar, and integer forms.
def amount_hint_score(amount: Decimal, candidate: EmailCandidate) -> float:
    text = f"{candidate.subject} {candidate.preview} {candidate.body_text}"
    candidates = {
        f"{amount:.2f}",
        f"{abs(amount):.2f}",
        f"${abs(amount):.2f}",
        str(int(abs(amount))),
    }
    normalized = normalized_text(text)
    for piece in candidates:
        if normalized_text(piece).strip() in normalized:
            return 1.0
    return 0.0


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
