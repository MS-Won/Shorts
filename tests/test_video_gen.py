import base64
from unittest.mock import patch, MagicMock
import pytest
from pipeline import video_gen


def _resp(json_body, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    r.content = b"fake-mp4-bytes"
    return r


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_submits_polls_and_downloads(mock_post, mock_get, tmp_path):
    start = tmp_path / "start.png"
    end = tmp_path / "end.png"
    start.write_bytes(b"start-bytes")
    end.write_bytes(b"end-bytes")
    out_path = str(tmp_path / "clip.mp4")

    mock_post.return_value = _resp({"task_id": "task-123"})
    responses = [
        _resp({"status": "Processing"}),
        _resp({"status": "Success", "file_id": "file-456"}),
        _resp({"file": {"download_url": "https://example.com/clip.mp4"}}),
        _resp({}),  # the final requests.get is the actual file download
    ]
    responses[-1].content = b"fake-mp4-bytes"
    mock_get.side_effect = responses

    result = video_gen.generate_video_segment(str(start), str(end), 5, out_path, poll_interval_sec=0)

    assert result == out_path
    with open(out_path, "rb") as f:
        assert f.read() == b"fake-mp4-bytes"


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_raises_on_task_failure(mock_post, mock_get, tmp_path):
    start = tmp_path / "start.png"
    end = tmp_path / "end.png"
    start.write_bytes(b"s")
    end.write_bytes(b"e")

    mock_post.return_value = _resp({"task_id": "task-123"})
    mock_get.side_effect = [_resp({"status": "Fail"})]

    with pytest.raises(video_gen.VideoGenerationError):
        video_gen.generate_video_segment(str(start), str(end), 5, str(tmp_path / "clip.mp4"),
                                          poll_interval_sec=0)


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_raises_after_max_polls(mock_post, mock_get, tmp_path):
    start = tmp_path / "start.png"
    end = tmp_path / "end.png"
    start.write_bytes(b"s")
    end.write_bytes(b"e")

    mock_post.return_value = _resp({"task_id": "task-123"})
    mock_get.return_value = _resp({"status": "Processing"})

    with pytest.raises(video_gen.VideoGenerationError, match="timed out"):
        video_gen.generate_video_segment(str(start), str(end), 5, str(tmp_path / "clip.mp4"),
                                          poll_interval_sec=0, max_polls=3)
