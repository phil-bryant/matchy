#!/usr/bin/env bats
# Numbered traceability tags: #R001-T01 #R005-T01 #R010-T01 #R010-T02 #R015-T01 #R015-T02 #R020-T01

@test "ai_ranker deterministic fallback is used when no AI keys exist" {
  #R001: Deterministic fallback path is used with no AI clients.
  #R001-T01: Confirm fallback rationale and selected ids.
  run env PYTHONPATH="$(pwd)" MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM="" MATCHY_OPENAI_API_KEY_1PSA_ITEM="" python3 -c "import matchy.settings as ms; ms.Settings._resolve_teller_db_password=lambda self:'pw'; from datetime import datetime, timezone; from decimal import Decimal; from matchy.ai_ranker import AiRanker; from matchy.models import TransactionInput, EmailCandidate, RankedCandidate; from matchy.settings import Settings; r=AiRanker(Settings(anthropic_api_key='', openai_api_key='')); t=TransactionInput('tx','acc',Decimal('10.00'),datetime.now(timezone.utc),'coffee'); c=[RankedCandidate(EmailCandidate('m1','receipt','preview',datetime.now(timezone.utc)),0.92,{}), RankedCandidate(EmailCandidate('m2','receipt2','preview',datetime.now(timezone.utc)),0.61,{})]; s=r.select(t,c); print(s.selected_message_ids==['m1','m2'] and 'deterministic fallback' in s.rationale)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "ai_ranker parse returns safe defaults for malformed json" {
  #R005: Malformed AI payloads produce safe default selections.
  #R005-T01: Confirm malformed json defaults.
  run env PYTHONPATH="$(pwd)" MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM="" MATCHY_OPENAI_API_KEY_1PSA_ITEM="" python3 -c "import matchy.settings as ms; ms.Settings._resolve_teller_db_password=lambda self:'pw'; from matchy.ai_ranker import AiRanker; from matchy.settings import Settings; r=AiRanker(Settings(anthropic_api_key='', openai_api_key='')); s=r._parse_ai_payload('{bad', 'anthropic'); print(s.selected_message_ids==[] and s.confidence==0.0 and s.uncertain is True)"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "ai_ranker extracts markup-free body excerpt for AI prompt" {
  #R010: _extract_body_excerpt strips HTML, collapses whitespace, and truncates the result.
  #R010-T01: HTML body with amount becomes plain text bounded by _BODY_TEXT_PROMPT_MAX.
  #R010-T02: Empty body_text resolves to empty string.
  run env PYTHONPATH="$(pwd)" MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM="" MATCHY_OPENAI_API_KEY_1PSA_ITEM="" python3 -c "
import matchy.settings as ms
ms.Settings._resolve_teller_db_password = lambda self: 'pw'
from matchy.ai_ranker import AiRanker
from matchy.settings import Settings
r = AiRanker(Settings(anthropic_api_key='', openai_api_key=''))
html = '<html><head><style>.x{}</style></head><body>  <p>Fare <strong>\$35.99</strong></p>  <script>x()</script>  thanks  </body></html>'
ex = r._extract_body_excerpt(html)
checks = [
    '<' not in ex,
    '>' not in ex,
    '\$35.99' in ex,
    'thanks' in ex,
    'x()' not in ex,
    '.x{}' not in ex,
    len(ex) <= r._BODY_TEXT_PROMPT_MAX,
    r._extract_body_excerpt('') == '',
    r._extract_body_excerpt('a' * 5000) == 'a' * r._BODY_TEXT_PROMPT_MAX,
]
print(all(checks))
"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "ai_ranker parser tolerates markdown json fences from claude" {
  #R015: Parse tolerates ```json ... ``` markdown fences and prose padding.
  #R015-T01: Verify a fence-wrapped JSON response parses to the inner selection fields.
  run env PYTHONPATH="$(pwd)" MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM="" MATCHY_OPENAI_API_KEY_1PSA_ITEM="" python3 -c "
import matchy.settings as ms
ms.Settings._resolve_teller_db_password = lambda self: 'pw'
from matchy.ai_ranker import AiRanker
from matchy.settings import Settings
r = AiRanker(Settings(anthropic_api_key='', openai_api_key=''))
raw = '\`\`\`json\n{\"selected_message_ids\":[\"m_correct\"],\"confidence\":0.95,\"uncertain\":false,\"rationale\":\"matches by amount\"}\n\`\`\`'
sel = r._parse_ai_payload(raw, 'anthropic')
print(sel.selected_message_ids == ['m_correct'] and abs(sel.confidence - 0.95) < 1e-6 and sel.uncertain is False and sel.rationale == 'matches by amount')
"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "ai_ranker parser extracts json object from surrounding prose" {
  #R015: Parse extracts the first balanced JSON object from prose-padded output.
  #R015-T02: Verify a JSON object surrounded by prose is still parsed.
  run env PYTHONPATH="$(pwd)" MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM="" MATCHY_OPENAI_API_KEY_1PSA_ITEM="" python3 -c "
import matchy.settings as ms
ms.Settings._resolve_teller_db_password = lambda self: 'pw'
from matchy.ai_ranker import AiRanker
from matchy.settings import Settings
r = AiRanker(Settings(anthropic_api_key='', openai_api_key=''))
raw = 'Here is my answer: {\"selected_message_ids\":[\"m1\",\"m2\"],\"confidence\":0.7,\"uncertain\":true,\"rationale\":\"two emails\"} let me know.'
sel = r._parse_ai_payload(raw, 'anthropic')
print(sel.selected_message_ids == ['m1','m2'] and sel.rationale == 'two emails')
"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "ai_ranker retries with shrunken body excerpt after anthropic 429" {
  #R020: Anthropic 429 triggers a retry with a smaller body excerpt cap.
  #R020-T01: Verify the retry path returns the parsed selection from the second call.
  run env PYTHONPATH="$(pwd)" "$(pwd)/matchy-venv/bin/python3" - <<'PY'
from datetime import datetime, timezone
from decimal import Decimal
import matchy.settings as ms
ms.Settings._resolve_teller_db_password = lambda self: 'pw'
from matchy.ai_ranker import AiRanker
from matchy.models import TransactionInput, EmailCandidate, RankedCandidate
from matchy.settings import Settings
from anthropic import RateLimitError

class FakeResponse:
    headers = {"retry-after": "0"}
    status_code = 429

class FakeRateLimit(RateLimitError):
    # Bypass Anthropic's strict __init__ (which wants an httpx.Response).
    def __init__(self):
        Exception.__init__(self, "rate limited")
        self.message = "rate limited"
        self.response = FakeResponse()

class FakeMsg:
    def __init__(self, text):
        class Block:
            def __init__(self, t): self.type='text'; self.text=t
        self.content = [Block(text)]

class FakeMessages:
    def __init__(self, responses): self.responses = responses; self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception): raise item
        return item

class FakeClient:
    def __init__(self, responses): self.messages = FakeMessages(responses)

ranker = AiRanker(Settings(anthropic_api_key='', openai_api_key=''))
ranker._anthropic_client = FakeClient([
    FakeRateLimit(),
    FakeMsg('{"selected_message_ids":["m1"],"confidence":0.9,"uncertain":false,"rationale":"ok"}'),
])
ranker._settings = Settings(anthropic_api_key='', openai_api_key='', anthropic_model='claude-sonnet-4-5')

txn = TransactionInput('t1','acc',Decimal('35.99'),datetime(2026,5,5,tzinfo=timezone.utc),'LYFT','')
cand = EmailCandidate('m1','subj','preview',datetime(2026,5,5,tzinfo=timezone.utc),'x@y','body')
result = ranker._select_with_anthropic(txn, [RankedCandidate(cand, 0.9, {})])
checks = [
    result.selected_message_ids == ['m1'],
    len(ranker._anthropic_client.messages.calls) == 2,
]
print(all(checks))
PY
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}

@test "ai_ranker prompt payload exposes body_excerpt to the AI model" {
  #R010: Prompt payload includes a body_excerpt field for each candidate so the AI can disambiguate.
  #R010-T01: Verify candidate row includes body_excerpt populated from EmailCandidate.body_text.
  run env PYTHONPATH="$(pwd)" MATCHY_ANTHROPIC_API_KEY_1PSA_ITEM="" MATCHY_OPENAI_API_KEY_1PSA_ITEM="" python3 -c "
from datetime import datetime, timezone
from decimal import Decimal
import matchy.settings as ms
ms.Settings._resolve_teller_db_password = lambda self: 'pw'
from matchy.ai_ranker import AiRanker
from matchy.models import TransactionInput, EmailCandidate, RankedCandidate
from matchy.settings import Settings
r = AiRanker(Settings(anthropic_api_key='', openai_api_key=''))
t = TransactionInput('txn1','acc',Decimal('35.99'),datetime(2026,5,5,tzinfo=timezone.utc),'LYFT','')
cand = EmailCandidate('m1','Your ride','preview',datetime(2026,5,5,tzinfo=timezone.utc),'x@y','<p>Fare \$35.99</p>')
payload = r._build_prompt_payload(t, [RankedCandidate(cand, 0.7, {})])
row = payload['candidates'][0]
print('body_excerpt' in row and 'Fare \$35.99' in row['body_excerpt'] and '<' not in row['body_excerpt'])
"
  [ "$status" -eq 0 ]
  [ "$output" = "True" ]
}
