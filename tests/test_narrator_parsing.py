from pitchside.agents.narrator import NarrationError, extract_json, parse_narrative


def test_extract_json_handles_fences_and_chatter():
    text = 'Here you go:\n```json\n{"statements": []}\n```\nHope that helps!'
    assert extract_json(text) == {"statements": []}


def test_extract_json_rejects_text_without_json():
    for bad in ("no json here", "{broken json", ""):
        try:
            extract_json(bad)
        except NarrationError:
            continue
        raise AssertionError(f"expected NarrationError for {bad!r}")


def test_parse_narrative_validates_shape():
    ok = parse_narrative({"statements": [{"text": "Hi", "event_ids": [1], "claims": {"minute": 3}}]})
    assert ok.source == "llm" and ok.statements[0].claims == {"minute": 3}
    for bad in ({}, {"statements": [{"nope": 1}]}, {"statements": "x"}):
        try:
            parse_narrative(bad)
        except NarrationError:
            continue
        raise AssertionError(f"expected NarrationError for {bad!r}")
