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
#R040: Relevance tokenization is implemented in scoring_core.relevance_tokens.
#R041: Document frequency counting is implemented in scoring_core.document_frequencies.
#R042: Inverse document frequency is implemented in scoring_core.inverse_document_frequency.
#R043: BM25 relevance scoring is implemented in scoring_core.bm25_score.
#R044: BM25 saturation is implemented in scoring_core.bm25_relevance.
#R045: Subset-sum reachability is implemented in scoring_core.subset_sum_reachable.
#R046: Amount reconciliation scoring is implemented in scoring_core.amount_reconciliation_score.
#R760: Decimal-to-cents normalization is implemented in scoring_core._decimal_to_cents.
#R761: Money-token cent extraction is implemented in scoring_core._extract_money_cents.
 #R005: Rank candidates by weighted heuristics and return results sorted by descending score.
 #R047: Blend corpus-aware BM25 relevance and subset-sum amount reconciliation into the weighted score
 #R047: while keeping the reason payload key set stable across every ranked candidate.
def rank_candidates(transaction: TransactionInput, candidates: list[EmailCandidate], already_matched_ids: set[str]) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    corpus = [f"{item.subject} {item.preview} {item.body_text}" for item in candidates]
    corpus_size = len(corpus)
    document_frequency_map = scoring_core.document_frequencies(corpus)
    total_token_length = sum(len(scoring_core.relevance_tokens(document)) for document in corpus)
    average_document_length = (total_token_length / corpus_size) if corpus_size else 0.0
    query_text = f"{transaction.counterparty_name} {transaction.description}"
    for item in candidates:
        text_blob = f"{item.subject} {item.preview} {item.body_text}"
        txn_blob = f"{transaction.description} {transaction.counterparty_name}"
        merchant_overlap = scoring_core.token_overlap(transaction.counterparty_name or transaction.description, text_blob)
        description_overlap = scoring_core.token_overlap(transaction.description, text_blob)
        amount_score = scoring_core.amount_hint_score(transaction.amount, item)
        compact_merchant_score = scoring_core.compact_merchant_hint_score(txn_blob, text_blob)
        sender_score = scoring_core.sender_hint_score(txn_blob, item.sender)
        time_score = scoring_core.time_proximity_score(transaction.date, item.received_at)
        bm25_relevance = scoring_core.bm25_relevance(
            scoring_core.bm25_score(query_text, text_blob, corpus_size, document_frequency_map, average_document_length)
        )
        reconciliation_score = scoring_core.amount_reconciliation_score(transaction.amount, item)
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
            + (bm25_relevance * 0.25)
            + (reconciliation_score * 0.15)
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
                    "bm25_relevance": round(bm25_relevance, 4),
                    "amount_reconciliation": round(reconciliation_score, 4),
                    "unmatched_email_priority": unmatched_priority,
                },
            )
        )
    ranked.sort(key=lambda row: row.score, reverse=True)
    return ranked
