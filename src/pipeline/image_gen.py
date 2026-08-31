"""Keyframe generation via Gemini's image models ("Nano Banana Pro").

Two kinds of keyframe come out of here: the single still behind a Ken Burns pan,
and the start/end pair that `video_gen.py` interpolates between. Both are
requested at 9:16 because the finished Short is vertical (spec §4.1).

API shape note: this uses the **Interactions API** (`/v1beta/interactions`,
`input` + `response_format`, response as `steps[].content[]`). The older
`models/{id}:generateContent` shape with `contents`/`parts`/`inlineData` is the
legacy API and does not accept an aspect ratio.
"""

import base64
import os

import requests

MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"

# 2K rather than 1K: a Ken Burns pan zooms *into* the still, so a frame at the
# video's own 1080px width would go soft as soon as it is scaled up.
IMAGE_SIZE = os.environ.get("GEMINI_IMAGE_SIZE", "2K")
ASPECT_RATIO = "9:16"


class ImageGenerationError(Exception):
    pass


def _extract_image_data(payload: dict) -> str:
    """Find the first base64 image anywhere in the response timeline.

    The model may emit a text part alongside the image ("Here is your image:"),
    and the step order is not guaranteed, so scan rather than index blindly.
    """
    for step in payload.get("steps", []):
        for item in step.get("content", []) or []:
            if item.get("type") == "image" and item.get("data"):
                return item["data"]
    raise ImageGenerationError(f"no image found in response: {payload}")


def generate_image(prompt: str, out_path: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ImageGenerationError("GEMINI_API_KEY is not set")

    response = requests.post(
        ENDPOINT,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "input": [{"type": "text", "text": prompt}],
            "response_format": {
                "type": "image",
                "mime_type": "image/png",
                "aspect_ratio": ASPECT_RATIO,
                "image_size": IMAGE_SIZE,
            },
        },
        timeout=120,
    )
    if response.status_code != 200:
        raise ImageGenerationError(
            f"image generation failed ({response.status_code}): {response.text}"
        )

    b64_data = _extract_image_data(response.json())

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return out_path
