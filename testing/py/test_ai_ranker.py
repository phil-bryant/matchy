#R001: Python test lane coverage for deterministic AI fallback.
#R005: Python test lane coverage for malformed JSON parsing.
#R010: Python test lane coverage for body excerpt extraction.
#R015: Python test lane coverage for markdown fence parsing.
#R020: Python test lane coverage for Anthropic 429 retry behavior.
#R001-T01: Python test lane exists for deterministic fallback requirement.
#R005-T01: Python test lane exists for malformed JSON requirement.
#R010-T01: Python test lane exists for body excerpt requirement.
#R010-T02: Python test lane exists for prompt payload body_excerpt requirement.
#R015-T01: Python test lane exists for markdown fence parsing requirement.
#R015-T02: Python test lane exists for prose-padded JSON requirement.
#R020-T01: Python test lane exists for Anthropic 429 retry requirement.

from datetime import datetime, timezone
from decimal import Decimal

from matchy.ai_ranker import AiRanker
from matchy.models import EmailCandidate, RankedCandidate, TransactionInput
from matchy.settings import Settings


def test_ai_ranker_deterministic_fallback_is_used_when_no_ai_keys_exist() -> None:
    #R001: Deterministic fallback path is used with no AI clients.
    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    txn = TransactionInput("tx", "acc", Decimal("10.00"), datetime.now(timezone.utc), "coffee")
    candidates = [
        RankedCandidate(EmailCandidate("m1", "receipt", "preview", datetime.now(timezone.utc)), 0.92, {}),
        RankedCandidate(EmailCandidate("m2", "receipt2", "preview", datetime.now(timezone.utc)), 0.61, {}),
    ]
    selection = ranker.select(txn, candidates)
    assert selection.selected_message_ids == ["m1", "m2"]
    assert "deterministic fallback" in selection.rationale


def test_ai_ranker_parse_returns_safe_defaults_for_malformed_json() -> None:
    #R005: Malformed AI payloads produce safe default selections.
    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    selection = ranker._parse_ai_payload("{bad", "anthropic")
    assert selection.selected_message_ids == []
    assert selection.confidence == 0.0
    assert selection.uncertain is True


def test_ai_ranker_extracts_markup_free_body_excerpt_for_ai_prompt() -> None:
    #R010: _extract_body_excerpt strips HTML, collapses whitespace, and truncates the result.
    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    html = '<html><head><style>.x{}</style></head><body>  <p>Fare <strong>$35.99</strong></p>  <script>x()</script>  thanks  </body></html>'
    excerpt = ranker._extract_body_excerpt(html)
    assert "<" not in excerpt
    assert ">" not in excerpt
    assert "$35.99" in excerpt
    assert "thanks" in excerpt
    assert "x()" not in excerpt
    assert ".x{}" not in excerpt
    assert len(excerpt) <= ranker._BODY_TEXT_PROMPT_MAX
    assert ranker._extract_body_excerpt("") == ""
    assert ranker._extract_body_excerpt("a" * 5000) == "a" * ranker._BODY_TEXT_PROMPT_MAX


def test_ai_ranker_parser_tolerates_markdown_json_fences_from_claude() -> None:
    #R015: Parse tolerates ```json ... ``` markdown fences and prose padding.
    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    raw = '```json\n{"selected_message_ids":["m_correct"],"confidence":0.95,"uncertain":false,"rationale":"matches by amount"}\n```'
    selection = ranker._parse_ai_payload(raw, "anthropic")
    assert selection.selected_message_ids == ["m_correct"]
    assert abs(selection.confidence - 0.95) < 1e-6
    assert selection.uncertain is False
    assert selection.rationale == "matches by amount"


def test_ai_ranker_parser_extracts_json_object_from_surrounding_prose() -> None:
    #R015: Parse extracts the first balanced JSON object from prose-padded output.
    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    raw = 'Here is my answer: {"selected_message_ids":["m1","m2"],"confidence":0.7,"uncertain":true,"rationale":"two emails"} let me know.'
    selection = ranker._parse_ai_payload(raw, "anthropic")
    assert selection.selected_message_ids == ["m1", "m2"]
    assert selection.rationale == "two emails"


def test_ai_ranker_retries_with_shrunken_body_excerpt_after_anthropic_429() -> None:
    #R020: Anthropic 429 triggers a retry with a smaller body excerpt cap.
    from anthropic import RateLimitError

    class FakeResponse:
        headers = {"retry-after": "0"}
        status_code = 429

    class FakeRateLimit(RateLimitError):
        def __init__(self):
            Exception.__init__(self, "rate limited")
            self.message = "rate limited"
            self.response = FakeResponse()

    class FakeMsg:
        def __init__(self, text):
            class Block:
                def __init__(self, t):
                    self.type = "text"
                    self.text = t

            self.content = [Block(text)]

    class FakeMessages:
        def __init__(self, responses):
            self.responses = responses
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            item = self.responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    class FakeClient:
        def __init__(self, responses):
            self.messages = FakeMessages(responses)

    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    ranker._anthropic_client = FakeClient([
        FakeRateLimit(),
        FakeMsg('{"selected_message_ids":["m1"],"confidence":0.9,"uncertain":false,"rationale":"ok"}'),
    ])
    ranker._settings = Settings(anthropic_api_key="", openai_api_key="", anthropic_model="claude-sonnet-4-5")
    txn = TransactionInput("t1", "acc", Decimal("35.99"), datetime(2026, 5, 5, tzinfo=timezone.utc), "LYFT", "")
    cand = EmailCandidate("m1", "subj", "preview", datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "body")
    result = ranker._select_with_anthropic(txn, [RankedCandidate(cand, 0.9, {})])
    assert result.selected_message_ids == ["m1"]
    assert len(ranker._anthropic_client.messages.calls) == 2


def test_ai_ranker_prompt_payload_exposes_body_excerpt_to_the_ai_model() -> None:
    #R010: Prompt payload includes a body_excerpt field for each candidate so the AI can disambiguate.
    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    txn = TransactionInput("txn1", "acc", Decimal("35.99"), datetime(2026, 5, 5, tzinfo=timezone.utc), "LYFT", "")
    cand = EmailCandidate("m1", "Your ride", "preview", datetime(2026, 5, 5, tzinfo=timezone.utc), "x@y", "<p>Fare $35.99</p>")
    payload = ranker._build_prompt_payload(txn, [RankedCandidate(cand, 0.7, {})])
    row = payload["candidates"][0]
    assert "body_excerpt" in row
    assert "Fare $35.99" in row["body_excerpt"]
    assert "<" not in row["body_excerpt"]
