import json
import random


class NoMusicAvailableError(Exception):
    pass


def _all_tracks(manifest: dict) -> list[str]:
    return [entry["file"] for tracks in manifest.values() for entry in tracks]


def pick_music(mood: str, manifest_path: str = "assets/music/manifest.json",
                used_recently: list[str] | None = None) -> str:
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    used_recently = used_recently or []
    candidates = [entry["file"] for entry in manifest.get(mood, [])]
    if not candidates:
        candidates = _all_tracks(manifest)
    if not candidates:
        raise NoMusicAvailableError(f"no music tracks found in {manifest_path}")

    unused = [c for c in candidates if c not in used_recently]
    pool = unused if unused else candidates
    return random.choice(pool)
