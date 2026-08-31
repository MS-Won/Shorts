import json
from unittest.mock import patch, MagicMock
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


_ALL_REQUIRED_ENV_VARS = {
    "ANTHROPIC_API_KEY": "anthropic-key",
    "GEMINI_API_KEY": "gemini-key",
    "MINIMAX_API_KEY": "minimax-key",
    "TELEGRAM_BOT_TOKEN": "telegram-token",
    "TELEGRAM_CHAT_ID": "telegram-chat",
    "YOUTUBE_CLIENT_ID": "yt-client-id",
    "YOUTUBE_CLIENT_SECRET": "yt-client-secret",
    "YOUTUBE_REFRESH_TOKEN": "yt-refresh-token",
}


@patch("pipeline.orchestrator._preflight_check", return_value=None)
@patch("pipeline.orchestrator.youtube_publish.publish_video")
@patch("pipeline.orchestrator.telegram_approval.request_approval")
@patch("pipeline.orchestrator.assemble.assemble_video")
@patch("pipeline.orchestrator.music.pick_music")
@patch("pipeline.orchestrator.video_gen.generate_video_segment")
@patch("pipeline.orchestrator.image_gen.generate_image")
@patch("pipeline.orchestrator.storyboard.generate_storyboard")
@patch("pipeline.orchestrator.ideas.generate_idea")
def test_run_pipeline_publishes_on_approval(mock_idea, mock_storyboard, mock_image, mock_video,
                                             mock_music, mock_assemble, mock_approval, mock_publish,
                                             mock_preflight,
                                             tmp_path, monkeypatch):
    mock_idea.return_value = IDEA
    mock_storyboard.return_value = STORYBOARD
    mock_image.side_effect = lambda prompt, out_path: out_path
    mock_video.side_effect = lambda s, e, d, out_path, **kw: out_path
    mock_music.return_value = "track.mp3"
    mock_assemble.return_value = str(tmp_path / "final.mp4")
    mock_approval.return_value = True
    mock_publish.return_value = "yt-video-999"

    # music_path is resolved relative to cwd (assets/music/<file>); create
    # the dummy track there so the existence check added for CRITICAL 2 passes.
    music_dir = tmp_path / "cwd" / "assets" / "music"
    music_dir.mkdir(parents=True)
    (music_dir / "track.mp3").write_bytes(b"fake-track")
    monkeypatch.chdir(tmp_path / "cwd")

    state_path = str(tmp_path / "history.json")
    result = orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=state_path)

    assert result == {"published": True, "youtube_id": "yt-video-999", "cost_usd": result["cost_usd"]}
    mock_publish.assert_called_once()
    saved = json.loads(open(state_path).read())
    assert len(saved["used_combos"]) == 1
    assert len(saved["published"]) == 1
    assert saved["published"][0]["youtube_id"] == "yt-video-999"

    # timeout for the approval gate must be well under the CI job's
    # timeout-minutes, not the telegram_approval module's 3600s default.
    _, approval_kwargs = mock_approval.call_args
    assert approval_kwargs["timeout_sec"] == 900


@patch("pipeline.orchestrator._preflight_check", return_value=None)
@patch("pipeline.orchestrator.youtube_publish.publish_video")
@patch("pipeline.orchestrator.telegram_approval.request_approval")
@patch("pipeline.orchestrator.assemble.assemble_video")
@patch("pipeline.orchestrator.music.pick_music")
@patch("pipeline.orchestrator.video_gen.generate_video_segment")
@patch("pipeline.orchestrator.image_gen.generate_image")
@patch("pipeline.orchestrator.storyboard.generate_storyboard")
@patch("pipeline.orchestrator.ideas.generate_idea")
def test_run_pipeline_does_not_publish_on_rejection(mock_idea, mock_storyboard, mock_image, mock_video,
                                                      mock_music, mock_assemble, mock_approval, mock_publish,
                                                      mock_preflight,
                                                      tmp_path, monkeypatch):
    mock_idea.return_value = IDEA
    mock_storyboard.return_value = STORYBOARD
    mock_image.side_effect = lambda prompt, out_path: out_path
    mock_video.side_effect = lambda s, e, d, out_path, **kw: out_path
    mock_music.return_value = "track.mp3"
    mock_assemble.return_value = str(tmp_path / "final.mp4")
    mock_approval.return_value = False

    music_dir = tmp_path / "cwd" / "assets" / "music"
    music_dir.mkdir(parents=True)
    (music_dir / "track.mp3").write_bytes(b"fake-track")
    monkeypatch.chdir(tmp_path / "cwd")

    state_path = str(tmp_path / "history.json")
    result = orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=state_path)

    assert result["published"] is False
    assert result["youtube_id"] is None
    mock_publish.assert_not_called()


@patch("pipeline.orchestrator.music.pick_music")
def test_run_pipeline_joins_picked_track_against_music_dir(mock_music, tmp_path, monkeypatch):
    # Regression test for CRITICAL 2: pick_music returns a bare filename;
    # orchestrator must join it against assets/music/ before handing it to
    # assemble_video, and must fail loudly (not hand ffmpeg a bogus path) if
    # the resolved file doesn't exist.
    for name, value in _ALL_REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(name, value)

    manifest_path = tmp_path / "assets" / "music" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"tense": [{"file": "tense_1.mp3", "attribution": ""}]}))
    monkeypatch.chdir(tmp_path)

    mock_music.return_value = "tense_1.mp3"  # bare filename, as pick_music actually returns

    with patch("pipeline.orchestrator.ideas.generate_idea", return_value=IDEA), \
         patch("pipeline.orchestrator.storyboard.generate_storyboard", return_value=STORYBOARD), \
         patch("pipeline.orchestrator.image_gen.generate_image", side_effect=lambda p, o: o), \
         patch("pipeline.orchestrator.video_gen.generate_video_segment", side_effect=lambda s, e, d, o, **kw: o):
        with pytest.raises(FileNotFoundError, match="tense_1.mp3"):
            orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=str(tmp_path / "history.json"))


def test_preflight_check_raises_on_missing_env_var(tmp_path, monkeypatch):
    for name, value in _ALL_REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    manifest_path = tmp_path / "assets" / "music" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"tense": [{"file": "tense_1.mp3", "attribution": ""}]}))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(EnvironmentError, match="TELEGRAM_BOT_TOKEN"):
        orchestrator._preflight_check()


def test_preflight_check_raises_on_missing_anthropic_api_key(tmp_path, monkeypatch):
    for name, value in _ALL_REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    manifest_path = tmp_path / "assets" / "music" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"tense": [{"file": "tense_1.mp3", "attribution": ""}]}))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
        orchestrator._preflight_check()


@patch("pipeline.orchestrator.youtube_publish.publish_video")
@patch("pipeline.orchestrator.telegram_approval.request_approval")
@patch("pipeline.orchestrator.assemble.assemble_video")
@patch("pipeline.orchestrator.music.pick_music")
@patch("pipeline.orchestrator.video_gen.generate_video_segment")
@patch("pipeline.orchestrator.image_gen.generate_image")
@patch("pipeline.orchestrator.storyboard.generate_storyboard")
@patch("pipeline.orchestrator.ideas.generate_idea")
def test_run_pipeline_raises_before_any_generation_when_env_var_missing(
        mock_idea, mock_storyboard, mock_image, mock_video, mock_music, mock_assemble,
        mock_approval, mock_publish, tmp_path, monkeypatch):
    for name, value in _ALL_REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)

    manifest_path = tmp_path / "assets" / "music" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"tense": [{"file": "tense_1.mp3", "attribution": ""}]}))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(EnvironmentError, match="YOUTUBE_REFRESH_TOKEN"):
        orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=str(tmp_path / "history.json"))

    mock_idea.assert_not_called()
    mock_storyboard.assert_not_called()
    mock_image.assert_not_called()
    mock_video.assert_not_called()
    mock_music.assert_not_called()
    mock_assemble.assert_not_called()
    mock_approval.assert_not_called()
    mock_publish.assert_not_called()


def test_preflight_check_raises_when_music_manifest_empty(tmp_path, monkeypatch):
    for name, value in _ALL_REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(name, value)

    manifest_path = tmp_path / "assets" / "music" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({}))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(EnvironmentError, match="manifest"):
        orchestrator._preflight_check()


def test_preflight_check_raises_when_music_manifest_missing(tmp_path, monkeypatch):
    for name, value in _ALL_REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.chdir(tmp_path)  # no assets/music/manifest.json under this cwd

    with pytest.raises(EnvironmentError, match="manifest"):
        orchestrator._preflight_check()
