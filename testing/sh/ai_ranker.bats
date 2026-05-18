#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01

@test "ai_ranker deterministic fallback is used when no AI keys exist" {
  #R001: Deterministic fallback path is used with no AI clients.
  #R001-T01: Confirm fallback rationale and selected ids.
  run env PYTHONPATH="$(pwd)" python3 -c "from datetime import datetime, timezone; from decimal import Decimal; from matchy.ai_ranker import AiRanker; from matchy.models import TransactionInput, EmailCandidate, RankedCandidate; from matchy.settings import Settings; r=AiRanker(Settings(teller_db_password='pw', anthropic_api_key='', openai_api_key='')); t=TransactionInput('tx','acc',Decimal('10.00'),datetime.now(timezone.utc),'coffee'); c=[RankedCandidate(EmailCandidate('m1','receipt','preview',datetime.now(timezone.utc)),0.92,{}), RankedCandidate(EmailCandidate('m2','receipt2','preview',datetime.now(timezone.utc)),0.61,{})]; s=r.select(t,c); print(s.selected_message_ids==['m1','m2'] and 'deterministic fallback' in s.rationale)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "ai_ranker parse returns safe defaults for malformed json" {
  #R005: Malformed AI payloads produce safe default selections.
  #R005-T01: Confirm malformed json defaults.
  run env PYTHONPATH="$(pwd)" python3 -c "from matchy.ai_ranker import AiRanker; from matchy.settings import Settings; r=AiRanker(Settings(teller_db_password='pw', anthropic_api_key='', openai_api_key='')); s=r._parse_ai_payload('{bad', 'anthropic'); print(s.selected_message_ids==[] and s.confidence==0.0 and s.uncertain is True)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
