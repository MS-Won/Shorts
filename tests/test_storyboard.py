import json
import pytest
from pipeline import storyboard


IDEA = {
    "location": "inside a school bus",
    "concept": "post-apocalyptic bunker",
    "hook": "hidden room behind the driver's seat",
    "visual_style": "photorealistic",
    "audio_mood": "tense and driving",
}

VALID_STORYBOARD = {
    "beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "empty rusty school bus exterior",
         "pan": "in", "duration_sec": 4, "caption": "found this abandoned school bus..."},
        {"stage": "progress", "type": "transform_video", "prompt_start": "gutted school bus interior",
         "prompt_end": "half-built bunker interior with metal walls", "duration_sec": 5,
         "caption": "day 1: stripping it down"},
        {"stage": "twist", "type": "transform_video", "prompt_start": "half-built bunker interior",
         "prompt_end": "bunker interior revealing a hidden steel door", "duration_sec": 5,
         "caption": "wait... there's a hidden room?"},
        {"stage": "reveal", "type": "still_pan", "prompt": "finished bunker school bus interior, dramatic lighting",
         "pan": "out", "duration_sec": 4, "caption": "the finished bunker bus"},
        {"stage": "reveal", "type": "transform_video", "prompt_start": "bunker bus interior daytime",
         "prompt_end": "bunker bus interior with lights on at night", "duration_sec": 5,
         "caption": "home sweet bunker"},
        {"stage": "progress", "type": "transform_video", "prompt_start": "bare metal walls",
         "prompt_end": "insulated and painted walls", "duration_sec": 5,
         "caption": "insulating everything"},
        {"stage": "setup", "type": "still_pan", "prompt": "tools laid out before starting",
         "pan": "left", "duration_sec": 4, "caption": "let's get started"},
    ],
    "title": "I Turned an Abandoned School Bus Into a Secret Bunker",
    "description": "Watch this school bus get transformed into a hidden bunker, room by room.",
    "tags": ["ai build", "bunker", "school bus", "shorts"],
}


def test_generate_storyboard_returns_parsed_dict():
    def fake_llm(prompt, **kwargs):
        return json.dumps(VALID_STORYBOARD)

    result = storyboard.generate_storyboard(IDEA, call_llm=fake_llm)
    assert result["title"] == VALID_STORYBOARD["title"]
    assert len(result["beats"]) == 7


def test_generate_storyboard_includes_idea_axes_in_prompt():
    captured = {}

    def fake_llm(prompt, **kwargs):
        captured["prompt"] = prompt
        return json.dumps(VALID_STORYBOARD)

    storyboard.generate_storyboard(IDEA, call_llm=fake_llm)
    assert "school bus" in captured["prompt"]
    assert "hidden room behind the driver's seat" in captured["prompt"]


def test_generate_storyboard_strips_markdown_fences():
    def fake_llm(prompt, **kwargs):
        return "```json\n" + json.dumps(VALID_STORYBOARD) + "\n```"

    assert storyboard.generate_storyboard(IDEA, call_llm=fake_llm)["title"]


def test_generate_storyboard_retries_when_validation_fails_then_succeeds():
    too_short = dict(VALID_STORYBOARD)
    too_short["beats"] = VALID_STORYBOARD["beats"][:1]  # only 4 sec, fails min duration + stage coverage
    calls = {"count": 0}

    def fake_llm(prompt, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(too_short)
        return json.dumps(VALID_STORYBOARD)

    result = storyboard.generate_storyboard(IDEA, call_llm=fake_llm)
    assert len(result["beats"]) == 7
    assert calls["count"] == 2


def test_generate_storyboard_retries_when_json_is_not_an_object():
    calls = {"count": 0}

    def fake_llm(prompt, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return '["not", "an", "object"]'
        return json.dumps(VALID_STORYBOARD)

    assert storyboard.generate_storyboard(IDEA, call_llm=fake_llm)["title"]
    assert calls["count"] == 2


def test_validate_storyboard_rejects_under_30_seconds():
    bad = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
         "duration_sec": 5, "caption": "x"},
    ], "title": "t", "description": "d", "tags": []}
    with pytest.raises(storyboard.StoryboardValidationError, match="30"):
        storyboard.validate_storyboard(bad)


def test_validate_storyboard_rejects_missing_stage():
    beats = [dict(b) for b in VALID_STORYBOARD["beats"]]
    for b in beats:
        if b["stage"] == "twist":
            b["stage"] = "progress"  # remove the only "twist" beat
    bad = {**VALID_STORYBOARD, "beats": beats}
    with pytest.raises(storyboard.StoryboardValidationError, match="twist"):
        storyboard.validate_storyboard(bad)


def test_validate_storyboard_rejects_non_numeric_duration():
    beats = [dict(b) for b in VALID_STORYBOARD["beats"]]
    beats[0]["duration_sec"] = "four"
    with pytest.raises(storyboard.StoryboardValidationError, match="duration_sec"):
        storyboard.validate_storyboard({**VALID_STORYBOARD, "beats": beats})


def test_validate_storyboard_rejects_unknown_beat_type():
    beats = [dict(b) for b in VALID_STORYBOARD["beats"]]
    beats[0]["type"] = "interpretive_dance"
    with pytest.raises(storyboard.StoryboardValidationError, match="interpretive_dance"):
        storyboard.validate_storyboard({**VALID_STORYBOARD, "beats": beats})


def test_validate_storyboard_rejects_transform_video_missing_prompts():
    beats = [dict(b) for b in VALID_STORYBOARD["beats"]]
    beats[1].pop("prompt_end")
    with pytest.raises(storyboard.StoryboardValidationError, match="prompt_end"):
        storyboard.validate_storyboard({**VALID_STORYBOARD, "beats": beats})


def test_validate_storyboard_rejects_still_pan_with_bad_pan_direction():
    beats = [dict(b) for b in VALID_STORYBOARD["beats"]]
    beats[0]["pan"] = "diagonally"
    with pytest.raises(storyboard.StoryboardValidationError, match="pan"):
        storyboard.validate_storyboard({**VALID_STORYBOARD, "beats": beats})


def test_validate_storyboard_accepts_valid_storyboard():
    storyboard.validate_storyboard(VALID_STORYBOARD)  # should not raise
