from __future__ import annotations

from .models import EmailCandidate, RankedCandidate, TransactionInput
from . import scoring_core

#R001: Normalization and overlap helpers live in scoring_core.
#R010: Normalization charset rules are implemented in scoring_core.normalized_text.
#R015: Token overlap ratio is implemented in scoring_core.token_overlap.
#R020: Amount hint detection is implemented in scoring_core.amount_hint_score.
#R025: Sender hint detection is implemented in scoring_core.sender_hint_score.
#R030: Compact merchant hints are implemented in scoring_core.compact_merchant_hint_score.
#R035: Time proximity buckets are implemented in scoring_core.time_proximity_score.
 #R005: Rank candidates by weighted heuristics and return results sorted by descending score.
def rank_candidates(transaction: TransactionInput, candidates: list[EmailCandidate], already_matched_ids: set[str]) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for item in candidates:
        text_blob = f"{item.subject} {item.preview} {item.body_text}"
        txn_blob = f"{transaction.description} {transaction.counterparty_name}"
        merchant_overlap = scoring_core.token_overlap(transaction.counterparty_name or transaction.description, text_blob)
        description_overlap = scoring_core.token_overlap(transaction.description, text_blob)
        amount_score = scoring_core.amount_hint_score(transaction.amount, item)
        compact_merchant_score = scoring_core.compact_merchant_hint_score(txn_blob, text_blob)
        sender_score = scoring_core.sender_hint_score(txn_blob, item.sender)
        time_score = scoring_core.time_proximity_score(transaction.date, item.received_at)
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
