#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

@test "models transactioninput is immutable" {
  #R001: Dataclasses are frozen to prevent post-construction mutation.
  #R001-T01: Verify reassignment raises FrozenInstanceError.
  run env PYTHONPATH="$(pwd)" python3 -c "from datetime import datetime; from decimal import Decimal; from dataclasses import FrozenInstanceError; from matchy.models import TransactionInput; t=TransactionInput('tx','acc',Decimal('1.00'),datetime.utcnow(),'desc'); ok=False
try:
 t.description='new'
except FrozenInstanceError:
 ok=True
print(ok)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "models rankedcandidate reasons defaults are independent" {
  #R005: RankedCandidate reasons dict defaults are per instance.
  #R005-T01: Verify reasons dicts are not shared.
  run env PYTHONPATH="$(pwd)" python3 -c "from datetime import datetime; from matchy.models import EmailCandidate, RankedCandidate; c=EmailCandidate('m','s','p',datetime.utcnow()); a=RankedCandidate(c,0.2); b=RankedCandidate(c,0.3); a.reasons['x']=1; print('x' not in b.reasons)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
