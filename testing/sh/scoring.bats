#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

@test "scoring normalization handles punctuation differences" {
  #R001: Token overlap works after punctuation normalization.
  #R001-T01: Verify punctuation-insensitive overlap contributes score.
  run env PYTHONPATH="$(pwd)" python3 -c "from datetime import datetime, timezone; from decimal import Decimal; from matchy.models import TransactionInput, EmailCandidate; from matchy.scoring import rank_candidates; txn=TransactionInput('tx','a',Decimal('10.00'),datetime.now(timezone.utc),'DoorDash order!',''); cand=EmailCandidate('m1','Doordash-order receipt','',datetime.now(timezone.utc)); ranked=rank_candidates(txn,[cand],set()); print(ranked[0].reasons['description_overlap']>0)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "scoring returns candidates sorted by descending score" {
  #R005: Ranking output is sorted highest score first.
  #R005-T01: Verify deterministic descending order.
  run env PYTHONPATH="$(pwd)" python3 -c "from datetime import datetime, timezone, timedelta; from decimal import Decimal; from matchy.models import TransactionInput, EmailCandidate; from matchy.scoring import rank_candidates; now=datetime.now(timezone.utc); txn=TransactionInput('tx','a',Decimal('10.00'),now,'Coffee shop','Coffee'); hi=EmailCandidate('m1','Coffee receipt','$10.00',now); lo=EmailCandidate('m2','Random newsletter','',now-timedelta(days=30)); ranked=rank_candidates(txn,[lo,hi],set()); print(ranked[0].candidate.message_id=='m1' and ranked[0].score>=ranked[1].score)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
