from unittest.mock import patch, MagicMock
import pytest
from pipeline import youtube_publish


def _resp(json_body, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    return r


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_returns_youtube_video_id(mock_post, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video-bytes")

    mock_post.side_effect = [
        _resp({"access_token": "token-abc"}),  # token refresh
        _resp({"id": "yt-video-123"}),          # upload
    ]

    result = youtube_publish.publish_video(str(video_path), "title", "desc", ["tag1", "tag2"])
    assert result == "yt-video-123"


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_sets_synthetic_media_disclosure(mock_post, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video-bytes")

    mock_post.side_effect = [
        _resp({"access_token": "token-abc"}),
        _resp({"id": "yt-video-123"}),
    ]

    youtube_publish.publish_video(str(video_path), "title", "desc", ["tag1"], contains_synthetic_media=True)

    upload_call = mock_post.call_args_list[1]
    metadata_json = upload_call.kwargs["files"]["metadata"][1]
    assert '"containsSyntheticMedia": true' in metadata_json or '"containsSyntheticMedia":true' in metadata_json


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_raises_on_upload_failure(mock_post, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video-bytes")

    mock_post.side_effect = [
        _resp({"access_token": "token-abc"}),
        _resp({"error": "quota exceeded"}, status_code=403),
    ]

    with pytest.raises(youtube_publish.YouTubePublishError):
        youtube_publish.publish_video(str(video_path), "title", "desc", ["tag1"])
