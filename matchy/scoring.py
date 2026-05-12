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
        merchant_overlap = _token_overlap(transaction.counterparty_name or transaction.description, text_blob)
        description_overlap = _token_overlap(transaction.description, text_blob)
        amount_score = _amount_hint_score(transaction.amount, item)
        time_score = _time_proximity_score(transaction.date, item.received_at)
        unmatched_priority = item.message_id not in already_matched_ids
        unmatched_bonus = 0.15 if unmatched_priority else 0.0
        score = min(
            1.0,
            (merchant_overlap * 0.30)
            + (description_overlap * 0.20)
            + (amount_score * 0.25)
            + (time_score * 0.25)
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
                    "time_proximity": round(time_score, 4),
                    "unmatched_email_priority": unmatched_priority,
                },
            )
        )
    ranked.sort(key=lambda row: row.score, reverse=True)
    return ranked
