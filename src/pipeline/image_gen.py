import base64
import os
import requests

_MODEL = "gemini-3-pro-image-preview"
_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"


class ImageGenerationError(Exception):
    pass


def generate_image(prompt: str, out_path: str) -> str:
    # Nudge the model toward a vertical, 9:16-friendly composition so the
    # downstream center-crop to 1080x1920 in assemble.py doesn't cut away a
    # large portion of a shot the model framed for square/landscape.
    full_prompt = f"{prompt}, vertical 9:16 aspect ratio, portrait orientation, centered composition"
    api_key = os.environ.get("GEMINI_API_KEY", "")
    response = requests.post(
        _ENDPOINT,
        params={"key": api_key},
        json={
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        },
        timeout=120,
    )
    if response.status_code != 200:
        raise ImageGenerationError(f"image generation failed ({response.status_code}): {response.text}")

    data = response.json()
    try:
        b64_data = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError) as exc:
        raise ImageGenerationError(f"unexpected response shape: {data}") from exc

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return out_path
