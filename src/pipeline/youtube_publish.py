import json
import os
import requests

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubePublishError(Exception):
    pass


def _get_access_token() -> str:
    response = requests.post(_TOKEN_URL, data={
        "client_id": os.environ.get("YOUTUBE_CLIENT_ID", ""),
        "client_secret": os.environ.get("YOUTUBE_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("YOUTUBE_REFRESH_TOKEN", ""),
        "grant_type": "refresh_token",
    }, timeout=30)
    if response.status_code != 200:
        raise YouTubePublishError(f"token refresh failed ({response.status_code}): {response.text}")
    return response.json()["access_token"]


def publish_video(video_path: str, title: str, description: str, tags: list[str],
                   contains_synthetic_media: bool = True) -> str:
    access_token = _get_access_token()

    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": contains_synthetic_media,
        },
    }

    with open(video_path, "rb") as f:
        response = requests.post(
            _UPLOAD_URL,
            params={"uploadType": "multipart", "part": "snippet,status"},
            headers={"Authorization": f"Bearer {access_token}"},
            files={
                "metadata": (None, json.dumps(metadata), "application/json"),
                "video": (os.path.basename(video_path), f, "video/mp4"),
            },
            timeout=600,
        )

    if response.status_code not in (200, 201):
        raise YouTubePublishError(f"upload failed ({response.status_code}): {response.text}")
    return response.json()["id"]
