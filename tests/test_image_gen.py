import base64
from unittest.mock import patch, MagicMock
from pipeline import image_gen


TINY_PNG_BASE64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake-png-bytes").decode()


def _fake_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"inlineData": {"mimeType": "image/png", "data": TINY_PNG_BASE64}}]
            }
        }]
    }
    return resp


@patch("pipeline.image_gen.requests.post")
def test_generate_image_writes_decoded_png_to_out_path(mock_post, tmp_path):
    mock_post.return_value = _fake_response()
    out_path = str(tmp_path / "keyframe.png")

    result = image_gen.generate_image("a rusty school bus exterior", out_path)

    assert result == out_path
    with open(out_path, "rb") as f:
        assert f.read() == base64.b64decode(TINY_PNG_BASE64)


@patch("pipeline.image_gen.requests.post")
def test_generate_image_sends_prompt_in_request_body(mock_post, tmp_path):
    mock_post.return_value = _fake_response()
    image_gen.generate_image("a rusty school bus exterior", str(tmp_path / "out.png"))

    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["contents"][0]["parts"][0]["text"] == "a rusty school bus exterior"


@patch("pipeline.image_gen.requests.post")
def test_generate_image_raises_on_non_200(mock_post, tmp_path):
    resp = MagicMock()
    resp.status_code = 400
    resp.text = "bad request"
    mock_post.return_value = resp

    import pytest
    with pytest.raises(image_gen.ImageGenerationError):
        image_gen.generate_image("prompt", str(tmp_path / "out.png"))
