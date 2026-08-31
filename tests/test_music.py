import json
import pytest
from pipeline import music


MANIFEST = {
    "tense and driving": [{"file": "tense_1.mp3", "attribution": ""}],
    "upbeat": [
        {"file": "upbeat_1.mp3", "attribution": ""},
        {"file": "upbeat_2.mp3", "attribution": ""},
    ],
}


def _write_manifest(tmp_path, data=MANIFEST):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_pick_music_returns_a_track_matching_mood(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    result = music.pick_music("tense and driving", manifest_path=manifest_path)
    assert result == "tense_1.mp3"


def test_pick_music_matches_mood_case_insensitively(tmp_path):
    # The idea generator writes freeform moods, so casing and stray whitespace vary.
    manifest_path = _write_manifest(tmp_path)
    assert music.pick_music("  Tense And Driving ", manifest_path=manifest_path) == "tense_1.mp3"


def test_pick_music_falls_back_to_any_track_when_mood_not_found(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    result = music.pick_music("completely unknown mood", manifest_path=manifest_path)
    assert result in {"tense_1.mp3", "upbeat_1.mp3", "upbeat_2.mp3"}


def test_pick_music_avoids_recently_used_when_alternative_exists(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    result = music.pick_music("upbeat", manifest_path=manifest_path, used_recently=["upbeat_1.mp3"])
    assert result == "upbeat_2.mp3"


def test_pick_music_reuses_a_recent_track_when_it_is_the_only_option(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    result = music.pick_music("tense and driving", manifest_path=manifest_path,
                              used_recently=["tense_1.mp3"])
    assert result == "tense_1.mp3"


def test_pick_music_raises_when_manifest_is_empty(tmp_path):
    manifest_path = _write_manifest(tmp_path, data={})
    with pytest.raises(music.NoMusicAvailableError):
        music.pick_music("anything", manifest_path=manifest_path)


def test_pick_music_raises_when_manifest_file_is_missing(tmp_path):
    with pytest.raises(music.NoMusicAvailableError):
        music.pick_music("anything", manifest_path=str(tmp_path / "nope.json"))
