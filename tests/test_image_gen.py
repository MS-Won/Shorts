import base64
from unittest.mock import patch, MagicMock

import pytest

from pipeline import image_gen


TINY_PNG_BASE64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake-png-bytes").decode()


def _fake_response(content=None):
    """A Gemini Interactions API response (steps -> model_output -> content)."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "id": "int_123",
        "status": "completed",
        "steps": [
            {"type": "user_input", "status": "done",
             "content": [{"type": "text", "text": "a rusty school bus exterior"}]},
            {"type": "model_output", "status": "done",
             "content": content if content is not None else
             [{"type": "image", "mime_type": "image/png", "data": TINY_PNG_BASE64}]},
        ],
    }
    return resp


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@patch("pipeline.image_gen.requests.post")
def test_generate_image_writes_decoded_png_to_out_path(mock_post, tmp_path):
    mock_post.return_value = _fake_response()
    out_path = str(tmp_path / "keyframe.png")

    result = image_gen.generate_image("a rusty school bus exterior", out_path)

    assert result == out_path
    with open(out_path, "rb") as f:
        assert f.read() == base64.b64decode(TINY_PNG_BASE64)


@patch("pipeline.image_gen.requests.post")
def test_generate_image_creates_missing_parent_directories(mock_post, tmp_path):
    mock_post.return_value = _fake_response()
    out_path = str(tmp_path / "nested" / "dir" / "keyframe.png")
    image_gen.generate_image("prompt", out_path)
    assert (tmp_path / "nested" / "dir" / "keyframe.png").exists()


@patch("pipeline.image_gen.requests.post")
def test_generate_image_sends_prompt_and_model_in_request_body(mock_post, tmp_path):
    mock_post.return_value = _fake_response()
    image_gen.generate_image("a rusty school bus exterior", str(tmp_path / "out.png"))

    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["model"] == image_gen.MODEL
    assert body["input"][0]["text"] == "a rusty school bus exterior"


@patch("pipeline.image_gen.requests.post")
def test_generate_image_requests_a_vertical_9_16_frame(mock_post, tmp_path):
    # Spec §4.1: the Short is vertical 1080x1920. A square keyframe would ruin
    # every Ken Burns pan built on it.
    mock_post.return_value = _fake_response()
    image_gen.generate_image("prompt", str(tmp_path / "out.png"))

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["response_format"]["aspect_ratio"] == "9:16"


@patch("pipeline.image_gen.requests.post")
def test_generate_image_sends_api_key_as_a_header_not_a_query_param(mock_post, tmp_path):
    mock_post.return_value = _fake_response()
    image_gen.generate_image("prompt", str(tmp_path / "out.png"))

    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["x-goog-api-key"] == "test-key"
    assert "params" not in kwargs


@patch("pipeline.image_gen.requests.post")
def test_generate_image_skips_text_parts_and_finds_the_image_part(mock_post, tmp_path):
    mock_post.return_value = _fake_response(content=[
        {"type": "text", "text": "Here is your image:"},
        {"type": "image", "mime_type": "image/png", "data": TINY_PNG_BASE64},
    ])
    out_path = str(tmp_path / "out.png")
    image_gen.generate_image("prompt", out_path)
    with open(out_path, "rb") as f:
        assert f.read() == base64.b64decode(TINY_PNG_BASE64)


@patch("pipeline.image_gen.requests.post")
def test_generate_image_raises_when_response_contains_no_image(mock_post, tmp_path):
    mock_post.return_value = _fake_response(content=[{"type": "text", "text": "I cannot do that"}])
    with pytest.raises(image_gen.ImageGenerationError):
        image_gen.generate_image("prompt", str(tmp_path / "out.png"))


@patch("pipeline.image_gen.requests.post")
def test_generate_image_raises_on_non_200(mock_post, tmp_path):
    resp = MagicMock()
    resp.status_code = 400
    resp.text = "bad request"
    mock_post.return_value = resp

    with pytest.raises(image_gen.ImageGenerationError):
        image_gen.generate_image("prompt", str(tmp_path / "out.png"))


@patch("pipeline.image_gen.requests.post")
def test_generate_image_raises_before_calling_the_api_when_key_is_missing(mock_post, tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(image_gen.ImageGenerationError, match="GEMINI_API_KEY"):
        image_gen.generate_image("prompt", str(tmp_path / "out.png"))
    mock_post.assert_not_called()
