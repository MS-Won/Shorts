import base64
import os
import time
import requests

_BASE_URL = "https://api.minimax.chat/v1"
_MODEL = "MiniMax-Hailuo-2.3"


class VideoGenerationError(Exception):
    pass


def _headers():
    return {"Authorization": f"Bearer {os.environ.get('MINIMAX_API_KEY', '')}"}


def _image_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def generate_video_segment(start_image_path: str, end_image_path: str, duration_sec: int,
                            out_path: str, poll_interval_sec: int = 5, max_polls: int = 60) -> str:
    submit_resp = requests.post(
        f"{_BASE_URL}/video_generation",
        headers=_headers(),
        json={
            "model": _MODEL,
            "first_frame_image": _image_to_b64(start_image_path),
            "last_frame_image": _image_to_b64(end_image_path),
            "duration": duration_sec,
        },
        timeout=60,
    )
    if submit_resp.status_code != 200:
        raise VideoGenerationError(f"submit failed ({submit_resp.status_code}): {submit_resp.text}")
    task_id = submit_resp.json()["task_id"]

    file_id = None
    for _ in range(max_polls):
        status_resp = requests.get(f"{_BASE_URL}/query/video_generation",
                                    headers=_headers(), params={"task_id": task_id}, timeout=30)
        status_body = status_resp.json()
        status = status_body.get("status")
        if status == "Success":
            file_id = status_body["file_id"]
            break
        if status == "Fail":
            raise VideoGenerationError(f"video generation task {task_id} failed: {status_body}")
        if poll_interval_sec:
            time.sleep(poll_interval_sec)
    if file_id is None:
        raise VideoGenerationError(f"video generation task {task_id} timed out after {max_polls} polls")

    retrieve_resp = requests.get(f"{_BASE_URL}/files/retrieve",
                                  headers=_headers(), params={"file_id": file_id}, timeout=30)
    download_url = retrieve_resp.json()["file"]["download_url"]

    file_resp = requests.get(download_url, timeout=120)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(file_resp.content)
    return out_path
