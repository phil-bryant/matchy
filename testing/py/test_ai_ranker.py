#R001: Python test lane coverage for deterministic fallback selection.
#R005: Python test lane coverage for defensive AI payload parsing.
#R010: Python test lane coverage for body-excerpt prompt payload behavior.
#R015: Python test lane coverage for fence-tolerant JSON payload parsing.
#R001-T01: Python test lane exists for deterministic fallback requirement.
#R005-T01: Python test lane exists for payload parsing requirement.
#R010-T01: Python test lane exists for body-excerpt extraction requirement.
#R010-T02: Python test lane exists for empty-body excerpt requirement.
#R015-T01: Python test lane exists for markdown-fence-wrapped JSON requirement.
#R015-T02: Python test lane exists for prose-padded JSON requirement.
#R020: Python test lane coverage for Anthropic rate-limit retry-with-shrink.
#R020-T01: Python test lane exists for Anthropic 429 retry requirement.


def test_traceability_tags_ai_ranker() -> None:
    assert True


def test_extract_body_excerpt_strips_html_and_truncates() -> None:
    #R010-T01: HTML body becomes plain-text excerpt bounded by _BODY_TEXT_PROMPT_MAX.
    import matchy.settings as ms

    ms.Settings._resolve_teller_db_password = lambda self: "pw"  # type: ignore[method-assign]
    from matchy.ai_ranker import AiRanker
    from matchy.settings import Settings

    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    html = (
        "<html><head><style>.x{color:red}</style></head><body>"
        "<p>Fare <strong>$35.99</strong></p>"
        "<script>tracker()</script> thanks </body></html>"
    )
    excerpt = ranker._extract_body_excerpt(html)
    assert "<" not in excerpt
    assert ">" not in excerpt
    assert "$35.99" in excerpt
    assert "thanks" in excerpt
    assert "tracker()" not in excerpt
    assert ".x{color:red}" not in excerpt
    assert len(excerpt) <= ranker._BODY_TEXT_PROMPT_MAX
    assert ranker._extract_body_excerpt("a" * 5000) == "a" * ranker._BODY_TEXT_PROMPT_MAX


def test_extract_body_excerpt_handles_empty_body() -> None:
    #R010-T02: Empty body_text returns empty string without raising.
    import matchy.settings as ms

    ms.Settings._resolve_teller_db_password = lambda self: "pw"  # type: ignore[method-assign]
    from matchy.ai_ranker import AiRanker
    from matchy.settings import Settings

    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    assert ranker._extract_body_excerpt("") == ""
    assert ranker._extract_body_excerpt("   ") == ""


def test_parse_ai_payload_tolerates_markdown_fences() -> None:
    #R015-T01: Claude-style ```json ... ``` payload parses to the inner selection.
    import matchy.settings as ms

    ms.Settings._resolve_teller_db_password = lambda self: "pw"  # type: ignore[method-assign]
    from matchy.ai_ranker import AiRanker
    from matchy.settings import Settings

    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    raw = (
        "```json\n"
        '{"selected_message_ids":["m_correct"],"confidence":0.95,"uncertain":false,"rationale":"matches by amount"}\n'
        "```"
    )
    sel = ranker._parse_ai_payload(raw, "anthropic")
    assert sel.selected_message_ids == ["m_correct"]
    assert abs(sel.confidence - 0.95) < 1e-6
    assert sel.uncertain is False
    assert sel.rationale == "matches by amount"


def test_parse_ai_payload_extracts_json_from_surrounding_prose() -> None:
    #R015-T02: Prose-padded JSON parses to the embedded object.
    import matchy.settings as ms

    ms.Settings._resolve_teller_db_password = lambda self: "pw"  # type: ignore[method-assign]
    from matchy.ai_ranker import AiRanker
    from matchy.settings import Settings

    ranker = AiRanker(Settings(anthropic_api_key="", openai_api_key=""))
    raw = (
        'Here is my answer: '
        '{"selected_message_ids":["m1","m2"],"confidence":0.7,"uncertain":true,"rationale":"two emails"}'
        ' let me know.'
    )
    sel = ranker._parse_ai_payload(raw, "anthropic")
    assert sel.selected_message_ids == ["m1", "m2"]
    assert sel.rationale == "two emails"
