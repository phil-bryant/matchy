#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

@test "models transactioninput is immutable" {
  #R001: Dataclasses are frozen to prevent post-construction mutation.
  #R001-T01: Verify reassignment raises FrozenInstanceError.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
from matchy.models import TransactionInput

item = TransactionInput("tx", "acc", Decimal("1.00"), datetime.now(timezone.utc), "desc")
ok = False
try:
    item.description = "new"
except FrozenInstanceError:
    ok = True
print(ok)
PY
  [ "$status" -eq 0 ]
  [[ "$output" == *"True" ]]
}

@test "models rankedcandidate reasons defaults are independent" {
  #R005: RankedCandidate reasons dict defaults are per instance.
  #R005-T01: Verify reasons dicts are not shared.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from datetime import datetime, timezone
from matchy.models import EmailCandidate, RankedCandidate

candidate = EmailCandidate("m", "s", "p", datetime.now(timezone.utc))
left = RankedCandidate(candidate, 0.2)
right = RankedCandidate(candidate, 0.3)
left.reasons["x"] = 1
print("x" not in right.reasons)
PY
  [ "$status" -eq 0 ]
  [[ "$output" == *"True" ]]
}
