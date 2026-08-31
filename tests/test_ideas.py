import json
import pytest
from pipeline import ideas


VALID_IDEA = {
    "location": "inside a school bus",
    "concept": "post-apocalyptic bunker",
    "hook": "hidden room behind the driver's seat",
    "visual_style": "photorealistic",
    "audio_mood": "tense and driving",
}
VALID_IDEA_JSON = json.dumps(VALID_IDEA)


def test_generate_idea_returns_parsed_five_axis_dict():
    def fake_llm(prompt, **kwargs):
        return VALID_IDEA_JSON

    result = ideas.generate_idea(recent=[], call_llm=fake_llm)
    assert set(result.keys()) == {"location", "concept", "hook", "visual_style", "audio_mood"}
    assert result["location"] == "inside a school bus"


def test_generate_idea_key_order_is_stable():
    # The idea is written into state/history.json, which is committed to the repo.
    # Hash-random key order would produce a noisy diff on every run.
    def fake_llm(prompt, **kwargs):
        return VALID_IDEA_JSON

    first = ideas.generate_idea(recent=[], call_llm=fake_llm)
    assert list(first.keys()) == ["location", "concept", "hook", "visual_style", "audio_mood"]


def test_generate_idea_includes_recent_combos_in_prompt_to_avoid_repeats():
    captured = {}

    def fake_llm(prompt, **kwargs):
        captured["prompt"] = prompt
        return VALID_IDEA_JSON

    recent = [{"location": "amazon warehouse", "concept": "luxury", "hook": "x",
               "visual_style": "y", "audio_mood": "z"}]
    ideas.generate_idea(recent=recent, call_llm=fake_llm)
    assert "amazon warehouse" in captured["prompt"]


def test_generate_idea_strips_markdown_fences():
    def fake_llm(prompt, **kwargs):
        return f"```json\n{VALID_IDEA_JSON}\n```"

    assert ideas.generate_idea(recent=[], call_llm=fake_llm)["concept"] == "post-apocalyptic bunker"


def test_generate_idea_retries_on_invalid_json_then_succeeds():
    calls = {"count": 0}

    def fake_llm(prompt, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return "not json"
        return VALID_IDEA_JSON

    result = ideas.generate_idea(recent=[], call_llm=fake_llm)
    assert result["concept"] == "post-apocalyptic bunker"
    assert calls["count"] == 2


def test_generate_idea_retries_when_json_is_not_an_object():
    calls = {"count": 0}

    def fake_llm(prompt, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return '["a", "list", "not", "an", "object"]'
        return VALID_IDEA_JSON

    assert ideas.generate_idea(recent=[], call_llm=fake_llm)["location"] == "inside a school bus"
    assert calls["count"] == 2


def test_generate_idea_retries_when_a_required_key_is_missing():
    calls = {"count": 0}
    incomplete = json.dumps({"location": "a cave", "concept": "minimal"})

    def fake_llm(prompt, **kwargs):
        calls["count"] += 1
        return incomplete if calls["count"] == 1 else VALID_IDEA_JSON

    assert ideas.generate_idea(recent=[], call_llm=fake_llm)["hook"]
    assert calls["count"] == 2


def test_generate_idea_raises_after_max_attempts_of_invalid_json():
    def fake_llm(prompt, **kwargs):
        return "not json"

    with pytest.raises(ideas.IdeaGenerationError):
        ideas.generate_idea(recent=[], call_llm=fake_llm, max_attempts=2)
