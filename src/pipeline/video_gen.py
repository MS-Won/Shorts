"""Hailuo first-last-frame video segments — the only genuinely expensive step.

Cost is ~$0.01–0.03 per generated second, which is why only the `transform_video`
beats come through here; everything else is a Ken Burns pan over a still
(spec §5). The API is async: submit -> poll -> resolve a download URL -> fetch.
"""

import base64
import mimetypes
import os
import time

import requests

BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-Hailuo-2.3")
RESOLUTION = os.environ.get("MINIMAX_RESOLUTION", "1080P")

# The model accepts only a fixed set of clip lengths. The storyboard writes
# whatever it likes (typically 5s), so requests get snapped to the nearest
# supported value rather than rejected at submit time.
SUPPORTED_DURATIONS_SEC = (6, 10)

_SUCCESS_STATUSES = {"success"}
_FAILURE_STATUSES = {"fail", "failed", "failure"}


class VideoGenerationError(Exception):
    pass


def _api_key() -> str:
    key = os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        raise VideoGenerationError("MINIMAX_API_KEY is not set")
    return key


def _headers() -> dict:
    return {"Authorization": f"Bearer {_api_key()}"}


def _image_to_data_uri(path: str) -> str:
    """Encode as a data URI — a bare base64 string is rejected by the API."""
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{encoded}"


def _snap_duration(duration_sec: int) -> int:
    return min(SUPPORTED_DURATIONS_SEC, key=lambda supported: abs(supported - duration_sec))


def _check_business_error(body: dict, what: str) -> dict:
    """MiniMax reports failures inside a 200 response, via `base_resp`."""
    base_resp = body.get("base_resp") or {}
    status_code = base_resp.get("status_code", 0)
    if status_code:
        raise VideoGenerationError(
            f"{what} failed (base_resp.status_code={status_code}): {base_resp.get('status_msg')}"
        )
    return body


def generate_video_segment(start_image_path: str, end_image_path: str, duration_sec: int,
                           out_path: str, prompt: str | None = None,
                           poll_interval_sec: int = 5, max_polls: int = 60) -> str:
    headers = _headers()

    payload = {
        "model": MODEL,
        "first_frame_image": _image_to_data_uri(start_image_path),
        "last_frame_image": _image_to_data_uri(end_image_path),
        "duration": _snap_duration(duration_sec),
        "resolution": RESOLUTION,
    }
    if prompt:
        payload["prompt"] = prompt

    submit_resp = requests.post(
        f"{BASE_URL}/video_generation", headers=headers, json=payload, timeout=60
    )
    if submit_resp.status_code != 200:
        raise VideoGenerationError(f"submit failed ({submit_resp.status_code}): {submit_resp.text}")
    submit_body = _check_business_error(submit_resp.json(), "submit")
    task_id = submit_body.get("task_id")
    if not task_id:
        raise VideoGenerationError(f"submit returned no task_id: {submit_body}")

    file_id = None
    for _ in range(max_polls):
        status_resp = requests.get(f"{BASE_URL}/query/video_generation",
                                   headers=headers, params={"task_id": task_id}, timeout=30)
        status_body = _check_business_error(status_resp.json(), "status query")
        # Casing has moved around between API revisions ("Success" vs "success",
        # "Fail" vs "failed"), so compare case-insensitively.
        status = str(status_body.get("status", "")).casefold()
        if status in _SUCCESS_STATUSES:
            file_id = status_body.get("file_id")
            if not file_id:
                raise VideoGenerationError(f"task {task_id} succeeded but returned no file_id")
            break
        if status in _FAILURE_STATUSES:
            raise VideoGenerationError(f"video generation task {task_id} failed: {status_body}")
        if poll_interval_sec:
            time.sleep(poll_interval_sec)
    if file_id is None:
        raise VideoGenerationError(
            f"video generation task {task_id} timed out after {max_polls} polls"
        )

    retrieve_resp = requests.get(f"{BASE_URL}/files/retrieve",
                                 headers=headers, params={"file_id": file_id}, timeout=30)
    retrieve_body = _check_business_error(retrieve_resp.json(), "file retrieve")
    download_url = (retrieve_body.get("file") or {}).get("download_url")
    if not download_url:
        raise VideoGenerationError(f"no download_url in retrieve response: {retrieve_body}")

    file_resp = requests.get(download_url, timeout=120)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(file_resp.content)
    return out_path
