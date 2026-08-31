from unittest.mock import patch, MagicMock
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
                                             tmp_path):
    mock_idea.return_value = IDEA
    mock_storyboard.return_value = STORYBOARD
    mock_image.side_effect = lambda prompt, out_path: out_path
    mock_video.side_effect = lambda s, e, d, out_path, **kw: out_path
    mock_music.return_value = "track.mp3"
    mock_assemble.return_value = str(tmp_path / "final.mp4")
    mock_approval.return_value = True
    mock_publish.return_value = "yt-video-999"

    state_path = str(tmp_path / "history.json")
    result = orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=state_path)

    assert result == {"published": True, "youtube_id": "yt-video-999", "cost_usd": result["cost_usd"]}
    mock_publish.assert_called_once()
    import json
    saved = json.loads(open(state_path).read())
    assert len(saved["used_combos"]) == 1
    assert len(saved["published"]) == 1
    assert saved["published"][0]["youtube_id"] == "yt-video-999"


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
                                                      tmp_path):
    mock_idea.return_value = IDEA
    mock_storyboard.return_value = STORYBOARD
    mock_image.side_effect = lambda prompt, out_path: out_path
    mock_video.side_effect = lambda s, e, d, out_path, **kw: out_path
    mock_music.return_value = "track.mp3"
    mock_assemble.return_value = str(tmp_path / "final.mp4")
    mock_approval.return_value = False

    state_path = str(tmp_path / "history.json")
    result = orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=state_path)

    assert result["published"] is False
    assert result["youtube_id"] is None
    mock_publish.assert_not_called()
