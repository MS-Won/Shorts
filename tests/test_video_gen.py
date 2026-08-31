from unittest.mock import patch, MagicMock

import pytest

from pipeline import video_gen


def _resp(json_body, status_code=200, content=b"fake-mp4-bytes"):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    r.content = content
    r.text = str(json_body)
    return r


def _ok(body):
    """A MiniMax success envelope: base_resp.status_code == 0."""
    return _resp({**body, "base_resp": {"status_code": 0, "status_msg": "success"}})


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")


@pytest.fixture
def frames(tmp_path):
    start = tmp_path / "start.png"
    end = tmp_path / "end.png"
    start.write_bytes(b"start-bytes")
    end.write_bytes(b"end-bytes")
    return str(start), str(end)


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_submits_polls_and_downloads(mock_post, mock_get, frames, tmp_path):
    start, end = frames
    out_path = str(tmp_path / "clip.mp4")

    mock_post.return_value = _ok({"task_id": "task-123"})
    mock_get.side_effect = [
        _ok({"status": "Processing"}),
        _ok({"status": "Success", "file_id": "file-456"}),
        _ok({"file": {"download_url": "https://example.com/clip.mp4"}}),
        _resp({}, content=b"fake-mp4-bytes"),
    ]

    result = video_gen.generate_video_segment(start, end, 6, out_path, poll_interval_sec=0)

    assert result == out_path
    with open(out_path, "rb") as f:
        assert f.read() == b"fake-mp4-bytes"


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_submit_targets_the_official_host_and_sends_data_uri_frames(mock_post, mock_get, frames, tmp_path):
    start, end = frames
    mock_post.return_value = _ok({"task_id": "t"})
    mock_get.side_effect = [
        _ok({"status": "Success", "file_id": "f"}),
        _ok({"file": {"download_url": "https://example.com/clip.mp4"}}),
        _resp({}),
    ]

    video_gen.generate_video_segment(start, end, 6, str(tmp_path / "clip.mp4"), poll_interval_sec=0)

    args, kwargs = mock_post.call_args
    assert args[0].startswith("https://api.minimax.io/v1/")
    body = kwargs["json"]
    # A bare base64 string is rejected — the field takes a public URL or a data URI.
    assert body["first_frame_image"].startswith("data:image/png;base64,")
    assert body["last_frame_image"].startswith("data:image/png;base64,")
    assert body["model"] == video_gen.MODEL
    assert body["resolution"] == video_gen.RESOLUTION
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_submit_snaps_duration_to_a_supported_value(mock_post, mock_get, frames, tmp_path):
    # The storyboard writes 5s beats, but the model only accepts a fixed set of
    # durations — sending 5 would be rejected outright.
    start, end = frames
    mock_post.return_value = _ok({"task_id": "t"})
    mock_get.side_effect = [
        _ok({"status": "Success", "file_id": "f"}),
        _ok({"file": {"download_url": "https://example.com/clip.mp4"}}),
        _resp({}),
    ]

    video_gen.generate_video_segment(start, end, 5, str(tmp_path / "clip.mp4"), poll_interval_sec=0)

    assert mock_post.call_args[1]["json"]["duration"] in video_gen.SUPPORTED_DURATIONS_SEC


@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_raises_on_business_error_despite_http_200(mock_post, frames, tmp_path):
    # MiniMax returns HTTP 200 with a non-zero base_resp.status_code for things
    # like an exhausted balance. Checking only the HTTP code would sail past it.
    start, end = frames
    mock_post.return_value = _resp({"base_resp": {"status_code": 1008, "status_msg": "insufficient balance"}})

    with pytest.raises(video_gen.VideoGenerationError, match="1008"):
        video_gen.generate_video_segment(start, end, 6, str(tmp_path / "clip.mp4"), poll_interval_sec=0)


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
@pytest.mark.parametrize("failure_status", ["Fail", "failed", "FAILED"])
def test_generate_video_segment_raises_on_task_failure(mock_post, mock_get, failure_status, frames, tmp_path):
    start, end = frames
    mock_post.return_value = _ok({"task_id": "task-123"})
    mock_get.side_effect = [_ok({"status": failure_status})]

    with pytest.raises(video_gen.VideoGenerationError):
        video_gen.generate_video_segment(start, end, 6, str(tmp_path / "clip.mp4"), poll_interval_sec=0)


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_raises_after_max_polls(mock_post, mock_get, frames, tmp_path):
    start, end = frames
    mock_post.return_value = _ok({"task_id": "task-123"})
    mock_get.return_value = _ok({"status": "Processing"})

    with pytest.raises(video_gen.VideoGenerationError, match="timed out"):
        video_gen.generate_video_segment(start, end, 6, str(tmp_path / "clip.mp4"),
                                         poll_interval_sec=0, max_polls=3)
    assert mock_get.call_count == 3


@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_raises_before_calling_the_api_when_key_is_missing(
    mock_post, frames, tmp_path, monkeypatch
):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    start, end = frames
    with pytest.raises(video_gen.VideoGenerationError, match="MINIMAX_API_KEY"):
        video_gen.generate_video_segment(start, end, 6, str(tmp_path / "clip.mp4"))
    mock_post.assert_not_called()
