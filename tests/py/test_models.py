#R001: Python test lane coverage for model immutability behavior.
#R005: Python test lane coverage for per-instance reasons defaults.

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from matchy.models import EmailCandidate, RankedCandidate, TransactionInput


def test_models_transactioninput_is_immutable() -> None:
    #R001: Dataclasses are frozen to prevent post-construction mutation.
    #R001-T01: Python test lane exists for immutable dataclass requirement.
    item = TransactionInput("tx", "acc", Decimal("1.00"), datetime.now(timezone.utc), "desc")
    with pytest.raises(FrozenInstanceError):
        item.description = "new"


def test_models_rankedcandidate_reasons_defaults_are_independent() -> None:
    #R005: RankedCandidate reasons dict defaults are per instance.
    #R005-T01: Python test lane exists for independent reasons map requirement.
    candidate = EmailCandidate("m", "s", "p", datetime.now(timezone.utc))
    left = RankedCandidate(candidate, 0.2)
    right = RankedCandidate(candidate, 0.3)
    left.reasons["x"] = 1
    assert "x" not in right.reasons
