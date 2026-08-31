import json
import os
from pipeline import state


def test_load_state_returns_default_shape_when_file_missing(tmp_path):
    path = tmp_path / "history.json"
    result = state.load_state(str(path))
    assert result == {"used_combos": [], "cost_log": [], "published": []}


def test_save_then_load_roundtrips(tmp_path):
    path = tmp_path / "history.json"
    data = {"used_combos": [{"location": "school bus"}], "cost_log": [], "published": []}
    state.save_state(data, str(path))
    assert json.loads(path.read_text()) == data
    assert state.load_state(str(path)) == data


def test_record_combo_appends_with_timestamp():
    s = {"used_combos": [], "cost_log": [], "published": []}
    combo = {"location": "amazon warehouse", "concept": "luxury", "hook": "hidden room",
              "visual_style": "photoreal", "audio_mood": "upbeat"}
    state.record_combo(s, combo)
    assert len(s["used_combos"]) == 1
    assert s["used_combos"][0]["location"] == "amazon warehouse"
    assert "recorded_at" in s["used_combos"][0]


def test_recent_combos_returns_last_n_most_recent_first():
    s = {"used_combos": [], "cost_log": [], "published": []}
    for i in range(5):
        state.record_combo(s, {"location": f"place-{i}"})
    result = state.recent_combos(s, n=2)
    assert [c["location"] for c in result] == ["place-4", "place-3"]


def test_record_cost_appends_entry():
    s = {"used_combos": [], "cost_log": [], "published": []}
    state.record_cost(s, "vid-1", 3.75, {"images": 1.2, "video": 2.55})
    assert s["cost_log"] == [{"video_id": "vid-1", "cost_usd": 3.75,
                                "breakdown": {"images": 1.2, "video": 2.55}}]


def test_record_published_appends_entry():
    s = {"used_combos": [], "cost_log": [], "published": []}
    state.record_published(s, "vid-1", "yt-abc123", {"title": "Built inside a school bus"})
    assert s["published"] == [{"video_id": "vid-1", "youtube_id": "yt-abc123",
                                 "metadata": {"title": "Built inside a school bus"}}]
