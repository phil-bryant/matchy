from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class TransactionInput:
    transaction_id: str
    account_id: str
    amount: Decimal
    date: datetime
    description: str
    counterparty_name: str = ""


@dataclass(frozen=True)
class EmailCandidate:
    message_id: str
    subject: str
    preview: str
    received_at: datetime
    sender: str = ""
    body_text: str = ""


@dataclass(frozen=True)
class RankedCandidate:
    candidate: EmailCandidate
    score: float
    reasons: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AiSelection:
    selected_message_ids: list[str]
    confidence: float
    uncertain: bool
    rationale: str
