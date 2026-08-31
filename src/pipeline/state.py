"""Read/write helpers for `state/history.json`.

This module never touches the network. It owns the pipeline's only durable
memory: which 5-axis combos have been used, what each video cost, and what has
been published. The orchestrator commits the resulting file back to the repo so
the next scheduled run can avoid repeating itself.
"""

import json
import os
from datetime import datetime, timezone


def load_state(path: str = "state/history.json") -> dict:
    if not os.path.exists(path):
        return {"used_combos": [], "cost_log": [], "published": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, path: str = "state/history.json") -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def record_combo(state: dict, combo: dict) -> None:
    entry = dict(combo)
    entry["recorded_at"] = datetime.now(timezone.utc).isoformat()
    state["used_combos"].append(entry)


def recent_combos(state: dict, n: int = 20) -> list[dict]:
    return list(reversed(state["used_combos"][-n:]))


def record_cost(state: dict, video_id: str, cost_usd: float, breakdown: dict) -> None:
    state["cost_log"].append({
        "video_id": video_id,
        "cost_usd": cost_usd,
        "breakdown": breakdown,
    })


def record_published(state: dict, video_id: str, youtube_id: str, metadata: dict) -> None:
    state["published"].append({
        "video_id": video_id,
        "youtube_id": youtube_id,
        "metadata": metadata,
    })
