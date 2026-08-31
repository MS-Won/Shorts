"""Uploads the approved Short to YouTube.

`containsSyntheticMedia` is not optional for this channel. The videos show
buildings that do not exist in places that do, which is exactly the "could
mislead a viewer about a real place" case YouTube's disclosure policy covers
(spec §3.3). Skipping the declaration risks YouTube labelling the video itself
— a label that cannot be removed — or pulling ad revenue.
"""

import json
import os

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

# YouTube's own limits. Tripping one of these rejects the upload *after* the
# $3-5 of generation has already been spent, so trim rather than fail.
MAX_TITLE_CHARS = 100
MAX_DESCRIPTION_CHARS = 5000
MAX_TAGS_TOTAL_CHARS = 500


class YouTubePublishError(Exception):
    pass


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise YouTubePublishError(f"{name} is not set")
    return value


def _trim_tags(tags: list[str]) -> list[str]:
    kept, used = [], 0
    for tag in tags:
        if used + len(tag) > MAX_TAGS_TOTAL_CHARS:
            break
        kept.append(tag)
        used += len(tag)
    return kept


def _get_access_token() -> str:
    response = requests.post(TOKEN_URL, data={
        "client_id": _require("YOUTUBE_CLIENT_ID"),
        "client_secret": _require("YOUTUBE_CLIENT_SECRET"),
        "refresh_token": _require("YOUTUBE_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }, timeout=30)
    if response.status_code != 200:
        raise YouTubePublishError(f"token refresh failed ({response.status_code}): {response.text}")
    token = response.json().get("access_token")
    if not token:
        raise YouTubePublishError(f"token refresh returned no access_token: {response.text}")
    return token


def publish_video(video_path: str, title: str, description: str, tags: list[str],
                  contains_synthetic_media: bool = True) -> str:
    # Check credentials before doing anything else, so a misconfigured secret
    # fails immediately rather than part-way through an upload.
    for name in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        _require(name)

    access_token = _get_access_token()

    metadata = {
        "snippet": {
            "title": title[:MAX_TITLE_CHARS],
            "description": description[:MAX_DESCRIPTION_CHARS],
            "tags": _trim_tags(tags),
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
            UPLOAD_URL,
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
    video_id = response.json().get("id")
    if not video_id:
        raise YouTubePublishError(f"upload returned no video id: {response.text}")
    return video_id
