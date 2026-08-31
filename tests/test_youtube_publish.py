import json
from unittest.mock import patch, MagicMock

import pytest

from pipeline import youtube_publish


def _resp(json_body, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    r.text = str(json_body)
    return r


@pytest.fixture(autouse=True)
def _credentials(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "rtoken")


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "final.mp4"
    path.write_bytes(b"fake-video-bytes")
    return str(path)


def _ok_flow():
    return [_resp({"access_token": "token-abc"}), _resp({"id": "yt-video-123"})]


def _uploaded_metadata(mock_post) -> dict:
    return json.loads(mock_post.call_args_list[1].kwargs["files"]["metadata"][1])


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_returns_youtube_video_id(mock_post, video):
    mock_post.side_effect = _ok_flow()
    assert youtube_publish.publish_video(video, "title", "desc", ["tag1", "tag2"]) == "yt-video-123"


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_sets_synthetic_media_disclosure(mock_post, video):
    mock_post.side_effect = _ok_flow()
    youtube_publish.publish_video(video, "title", "desc", ["tag1"], contains_synthetic_media=True)
    assert _uploaded_metadata(mock_post)["status"]["containsSyntheticMedia"] is True


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_requests_the_snippet_and_status_parts(mock_post, video):
    mock_post.side_effect = _ok_flow()
    youtube_publish.publish_video(video, "title", "desc", ["tag1"])
    params = mock_post.call_args_list[1].kwargs["params"]
    assert "snippet" in params["part"] and "status" in params["part"]


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_truncates_an_over_long_title(mock_post, video):
    # YouTube rejects titles over 100 characters. Failing here would waste the
    # entire $3-5 of generation that already happened.
    mock_post.side_effect = _ok_flow()
    youtube_publish.publish_video(video, "T" * 250, "desc", ["tag1"])
    assert len(_uploaded_metadata(mock_post)["snippet"]["title"]) <= youtube_publish.MAX_TITLE_CHARS


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_truncates_an_over_long_description(mock_post, video):
    mock_post.side_effect = _ok_flow()
    youtube_publish.publish_video(video, "title", "D" * 6000, ["tag1"])
    description = _uploaded_metadata(mock_post)["snippet"]["description"]
    assert len(description) <= youtube_publish.MAX_DESCRIPTION_CHARS


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_trims_tags_to_the_total_length_budget(mock_post, video):
    mock_post.side_effect = _ok_flow()
    youtube_publish.publish_video(video, "title", "desc", [f"tag-number-{i}" for i in range(100)])
    tags = _uploaded_metadata(mock_post)["snippet"]["tags"]
    assert sum(len(t) for t in tags) <= youtube_publish.MAX_TAGS_TOTAL_CHARS


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_raises_on_upload_failure(mock_post, video):
    mock_post.side_effect = [
        _resp({"access_token": "token-abc"}),
        _resp({"error": "quota exceeded"}, status_code=403),
    ]
    with pytest.raises(youtube_publish.YouTubePublishError):
        youtube_publish.publish_video(video, "title", "desc", ["tag1"])


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_raises_on_token_refresh_failure(mock_post, video):
    mock_post.side_effect = [_resp({"error": "invalid_grant"}, status_code=400)]
    with pytest.raises(youtube_publish.YouTubePublishError, match="token refresh"):
        youtube_publish.publish_video(video, "title", "desc", ["tag1"])


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_raises_before_calling_the_api_when_credentials_are_missing(
    mock_post, video, monkeypatch
):
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)
    with pytest.raises(youtube_publish.YouTubePublishError, match="YOUTUBE_REFRESH_TOKEN"):
        youtube_publish.publish_video(video, "title", "desc", ["tag1"])
    mock_post.assert_not_called()
