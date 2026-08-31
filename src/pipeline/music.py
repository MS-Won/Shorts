"""Picks a royalty-free backing track for a video.

v1 has no narration, so the music is doing real work: it carries the mood and
the pacing (spec §4.1). Tracks come from YouTube's Audio Library, which has no
public API — see `assets/music/README.md` for the one-time manual step.
"""

import json
import os
import random


class NoMusicAvailableError(Exception):
    pass


def _all_tracks(manifest: dict) -> list[str]:
    return [entry["file"] for tracks in manifest.values() for entry in tracks]


def _tracks_for_mood(manifest: dict, mood: str) -> list[str]:
    """Look the mood up case-insensitively, ignoring surrounding whitespace.

    `audio_mood` is freeform text from the idea generator, so an exact-string
    match would miss "Upbeat" against a manifest key of "upbeat".
    """
    wanted = mood.strip().casefold()
    for key, entries in manifest.items():
        if key.strip().casefold() == wanted:
            return [entry["file"] for entry in entries]
    return []


def pick_music(mood: str, manifest_path: str = "assets/music/manifest.json",
               used_recently: list[str] | None = None) -> str:
    if not os.path.exists(manifest_path):
        # An unattended daily run should fail with the pipeline's own error type,
        # not a bare FileNotFoundError from deep inside the call stack.
        raise NoMusicAvailableError(f"music manifest not found at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    used_recently = used_recently or []
    candidates = _tracks_for_mood(manifest, mood)
    if not candidates:
        candidates = _all_tracks(manifest)
    if not candidates:
        raise NoMusicAvailableError(f"no music tracks found in {manifest_path}")

    unused = [c for c in candidates if c not in used_recently]
    pool = unused if unused else candidates
    return random.choice(pool)
