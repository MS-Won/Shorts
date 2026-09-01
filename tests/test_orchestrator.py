import json
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from pipeline import orchestrator


IDEA = {"location": "school bus", "concept": "bunker", "hook": "hidden room",
        "visual_style": "photoreal", "audio_mood": "tense"}
STORYBOARD = {
    "beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "p1", "pan": "in",
         "duration_sec": 15, "caption": "c1"},
        {"stage": "progress", "type": "transform_video", "prompt_start": "s1", "prompt_end": "e1",
         "duration_sec": 5, "caption": "c2"},
        {"stage": "twist", "type": "transform_video", "prompt_start": "s2", "prompt_end": "e2",
         "duration_sec": 5, "caption": "c3"},
        {"stage": "reveal", "type": "still_pan", "prompt": "p2", "pan": "out",
         "duration_sec": 8, "caption": "c4"},
    ],
    "title": "t", "description": "d", "tags": ["x"],
}

# 12 transform beats: 12 * (2 * $0.15 + 10 * $0.02) = $6.00, over the $5 ceiling.
EXPENSIVE_STORYBOARD = {
    "beats": [
        {"stage": "progress", "type": "transform_video", "prompt_start": f"s{i}",
         "prompt_end": f"e{i}", "duration_sec": 10, "caption": f"c{i}"}
        for i in range(12)
    ],
    "title": "t", "description": "d", "tags": ["x"],
}


@pytest.fixture
def mocks(tmp_path):
    """Patch every collaborator — this test is about wiring, not their internals."""
    targets = {
        "idea": "pipeline.orchestrator.ideas.generate_idea",
        "storyboard": "pipeline.orchestrator.storyboard.generate_storyboard",
        "image": "pipeline.orchestrator.image_gen.generate_image",
        "video": "pipeline.orchestrator.video_gen.generate_video_segment",
        "music": "pipeline.orchestrator.music.pick_music",
        "assemble": "pipeline.orchestrator.assemble.assemble_video",
        "approval": "pipeline.orchestrator.telegram_approval.request_approval",
        "publish": "pipeline.orchestrator.youtube_publish.publish_video",
        "notify": "pipeline.orchestrator.telegram_approval.notify",
    }
    with ExitStack() as stack:
        m = {name: stack.enter_context(patch(target)) for name, target in targets.items()}
        m["idea"].return_value = IDEA
        m["storyboard"].return_value = STORYBOARD
        m["image"].side_effect = lambda prompt, out_path: out_path
        m["video"].side_effect = lambda s, e, d, out_path, **kw: out_path
        m["music"].return_value = "track.mp3"
        m["assemble"].return_value = str(tmp_path / "final.mp4")
        m["approval"].return_value = True
        m["publish"].return_value = "yt-video-999"
        yield m


def _run(tmp_path, **kwargs):
    return orchestrator.run_pipeline(
        work_dir=str(tmp_path / "work"), state_path=str(tmp_path / "history.json"), **kwargs
    )


def _saved_state(tmp_path):
    with open(tmp_path / "history.json", encoding="utf-8") as f:
        return json.load(f)


def test_run_pipeline_publishes_on_approval(mocks, tmp_path):
    result = _run(tmp_path)

    assert result["published"] is True
    assert result["youtube_id"] == "yt-video-999"
    mocks["publish"].assert_called_once()

    saved = _saved_state(tmp_path)
    assert len(saved["used_combos"]) == 1
    assert len(saved["published"]) == 1
    assert saved["published"][0]["youtube_id"] == "yt-video-999"


def test_run_pipeline_does_not_publish_on_rejection(mocks, tmp_path):
    mocks["approval"].return_value = False
    result = _run(tmp_path)

    assert result["published"] is False
    assert result["youtube_id"] is None
    mocks["publish"].assert_not_called()


def test_run_pipeline_records_the_spend_even_when_rejected(mocks, tmp_path):
    # The money is gone either way; not recording it would understate the real
    # cost per published video.
    mocks["approval"].return_value = False
    _run(tmp_path)

    saved = _saved_state(tmp_path)
    assert len(saved["cost_log"]) == 1
    assert saved["cost_log"][0]["cost_usd"] > 0
    assert len(saved["used_combos"]) == 1  # and the idea must not be reused tomorrow


def test_estimate_cost_matches_the_documented_cost_model():
    # 2 stills ($0.15 each) + 2 transforms (2 images + 5s of video each)
    expected = 2 * 0.15 + 2 * (2 * 0.15 + 5 * 0.02)
    assert orchestrator.estimate_cost(STORYBOARD) == pytest.approx(expected)


def test_run_pipeline_refuses_to_spend_when_the_storyboard_blows_the_budget(mocks, tmp_path):
    mocks["storyboard"].return_value = EXPENSIVE_STORYBOARD
    result = _run(tmp_path)

    assert result is None
    mocks["image"].assert_not_called()
    mocks["video"].assert_not_called()


def test_run_pipeline_retries_the_storyboard_when_the_first_is_too_expensive(mocks, tmp_path):
    mocks["storyboard"].side_effect = [EXPENSIVE_STORYBOARD, STORYBOARD]
    result = _run(tmp_path)

    assert result["published"] is True
    assert mocks["storyboard"].call_count == 2


def test_run_pipeline_returns_none_when_idea_generation_fails(mocks, tmp_path):
    from pipeline import ideas
    mocks["idea"].side_effect = ideas.IdeaGenerationError("no valid idea")
    assert _run(tmp_path) is None
    mocks["image"].assert_not_called()


def test_run_pipeline_returns_none_when_storyboard_generation_fails(mocks, tmp_path):
    from pipeline import storyboard as storyboard_module
    mocks["storyboard"].side_effect = storyboard_module.StoryboardValidationError("nope")
    assert _run(tmp_path) is None
    mocks["image"].assert_not_called()


def test_run_pipeline_passes_a_motion_prompt_to_the_video_model(mocks, tmp_path):
    _run(tmp_path)
    _, kwargs = mocks["video"].call_args
    assert kwargs.get("prompt")


def test_run_pipeline_generates_two_keyframes_per_transform_beat(mocks, tmp_path):
    _run(tmp_path)
    # 2 stills + 2 transforms x 2 keyframes = 6 images
    assert mocks["image"].call_count == 6
    assert mocks["video"].call_count == 2


def test_run_pipeline_gives_each_run_a_distinct_video_id(mocks, tmp_path):
    first = orchestrator._make_video_id(IDEA, STORYBOARD)
    second = orchestrator._make_video_id(IDEA, STORYBOARD)
    assert first != second


def _state_with_cost_log(entries):
    return {"used_combos": [], "cost_log": entries, "published": []}


def test_validation_guard_allows_when_under_budget_and_checkpoint(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 100.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 10)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)
    state_ = _state_with_cost_log([{"cost_usd": 4.0} for _ in range(5)])

    assert orchestrator._validation_guard(state_) is None


def test_validation_guard_blocks_when_budget_is_exhausted(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 20.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 100)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)
    state_ = _state_with_cost_log([{"cost_usd": 4.0} for _ in range(5)])  # $20.00 total

    reason = orchestrator._validation_guard(state_)
    assert reason is not None
    assert "예산" in reason


def test_validation_guard_blocks_at_the_checkpoint_boundary(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 1000.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 10)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)
    state_ = _state_with_cost_log([{"cost_usd": 1.0} for _ in range(10)])

    reason = orchestrator._validation_guard(state_)
    assert reason is not None
    assert "체크포인트" in reason


def test_validation_guard_allows_just_under_the_checkpoint_boundary(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 1000.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 10)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)
    state_ = _state_with_cost_log([{"cost_usd": 1.0} for _ in range(9)])

    assert orchestrator._validation_guard(state_) is None


def test_validation_guard_respects_a_raised_ack_count(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 1000.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 10)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 10)  # last checkpoint was reviewed
    state_ = _state_with_cost_log([{"cost_usd": 1.0} for _ in range(10)])

    assert orchestrator._validation_guard(state_) is None


def test_run_pipeline_refuses_to_run_when_validation_guard_blocks(mocks, tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 1.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 1000)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)

    state_path = tmp_path / "history.json"
    state_path.write_text(json.dumps(_state_with_cost_log([{"cost_usd": 5.0}])))

    result = orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=str(state_path))

    assert result is None
    mocks["idea"].assert_not_called()
    mocks["notify"].assert_called_once()
