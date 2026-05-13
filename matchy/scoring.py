from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from .models import EmailCandidate, RankedCandidate, TransactionInput


def _normalized_text(value: str) -> str:
    lowered = value.lower()
    return re.sub(r"[^a-z0-9\s]", " ", lowered)


def _token_overlap(left: str, right: str) -> float:
    left_tokens = {part for part in _normalized_text(left).split() if len(part) > 2}
    right_tokens = {part for part in _normalized_text(right).split() if len(part) > 2}
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return overlap / max(len(left_tokens), len(right_tokens))


def _amount_hint_score(amount: Decimal, candidate: EmailCandidate) -> float:
    text = f"{candidate.subject} {candidate.preview} {candidate.body_text}"
    candidates = {
        f"{amount:.2f}",
        f"{abs(amount):.2f}",
        f"${abs(amount):.2f}",
        str(int(abs(amount))),
    }
    normalized = _normalized_text(text)
    for piece in candidates:
        if _normalized_text(piece).strip() in normalized:
            return 1.0
    return 0.0


def _sender_hint_score(transaction_text: str, sender: str) -> float:
    normalized_txn = _normalized_text(transaction_text)
    normalized_sender = _normalized_text(sender)
    if not normalized_txn or not normalized_sender:
        return 0.0
    txn_tokens = {part for part in normalized_txn.split() if len(part) > 2}
    sender_tokens = {part for part in normalized_sender.split() if len(part) > 2}
    if not txn_tokens or not sender_tokens:
        return 0.0
    if txn_tokens & sender_tokens:
        return 1.0
    return 0.0


def _compact_merchant_hint_score(transaction_text: str, candidate_text: str) -> float:
    compact_candidate = re.sub(r"[^a-z0-9]", "", candidate_text.lower())
    if not compact_candidate:
        return 0.0
    normalized_txn = _normalized_text(transaction_text)
    txn_tokens = [part for part in normalized_txn.split() if len(part) >= 6 and not part.isdigit()]
    for token in txn_tokens:
        if token in compact_candidate:
            return 1.0
    return 0.0


def _time_proximity_score(txn_time: datetime, received_at: datetime) -> float:
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


def rank_candidates(transaction: TransactionInput, candidates: list[EmailCandidate], already_matched_ids: set[str]) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for item in candidates:
        text_blob = f"{item.subject} {item.preview} {item.body_text}"
        txn_blob = f"{transaction.description} {transaction.counterparty_name}"
        merchant_overlap = _token_overlap(transaction.counterparty_name or transaction.description, text_blob)
        description_overlap = _token_overlap(transaction.description, text_blob)
        amount_score = _amount_hint_score(transaction.amount, item)
        compact_merchant_score = _compact_merchant_hint_score(txn_blob, text_blob)
        sender_score = _sender_hint_score(txn_blob, item.sender)
        time_score = _time_proximity_score(transaction.date, item.received_at)
        unmatched_priority = item.message_id not in already_matched_ids
        unmatched_bonus = 0.15 if unmatched_priority else 0.0
        score = min(
            1.0,
            (merchant_overlap * 0.30)
            + (description_overlap * 0.20)
            + (amount_score * 0.15)
            + (compact_merchant_score * 0.20)
            + (sender_score * 0.10)
            + (time_score * 0.20)
            + unmatched_bonus,
        )
        ranked.append(
            RankedCandidate(
                candidate=item,
                score=score,
                reasons={
                    "merchant_overlap": round(merchant_overlap, 4),
                    "description_overlap": round(description_overlap, 4),
                    "amount_hint": round(amount_score, 4),
                    "compact_merchant_hint": round(compact_merchant_score, 4),
                    "sender_hint": round(sender_score, 4),
                    "time_proximity": round(time_score, 4),
                    "unmatched_email_priority": unmatched_priority,
                },
            )
        )
    ranked.sort(key=lambda row: row.score, reverse=True)
    return ranked
