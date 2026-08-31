import json
import os
from pipeline import state, ideas, storyboard, image_gen, video_gen, music, assemble, telegram_approval, youtube_publish

_IMAGE_COST_USD = 0.15
_VIDEO_COST_PER_SEC_USD = 0.02

_MUSIC_DIR = os.path.join("assets", "music")
_MUSIC_MANIFEST_PATH = os.path.join(_MUSIC_DIR, "manifest.json")

_REQUIRED_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "MINIMAX_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "YOUTUBE_CLIENT_ID",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_REFRESH_TOKEN",
]

# Keep well under the GitHub Actions job's timeout-minutes (see
# .github/workflows/daily-shorts.yml) so a slow-to-respond operator can't get
# the whole run killed after generation assets have already been paid for.
_APPROVAL_TIMEOUT_SEC = 900


def _preflight_check() -> None:
    """Fail fast, before any paid generation happens, if the run can't possibly succeed."""
    missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise EnvironmentError(
            f"missing required environment variable(s): {', '.join(missing)}"
        )

    if not os.path.exists(_MUSIC_MANIFEST_PATH):
        raise EnvironmentError(f"music manifest not found: {_MUSIC_MANIFEST_PATH}")
    with open(_MUSIC_MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    if not manifest or not any(manifest.get(mood) for mood in manifest):
        raise EnvironmentError(
            f"music manifest {_MUSIC_MANIFEST_PATH} has no usable tracks "
            "(needs at least one mood key with at least one track); "
            "see assets/music/README.md"
        )


def _generate_beat_asset(i: int, beat: dict, work_dir: str) -> tuple[str, float]:
    if beat["type"] == "still_pan":
        path = os.path.join(work_dir, f"beat_{i}_still.png")
        image_gen.generate_image(beat["prompt"], path)
        return path, _IMAGE_COST_USD
    start_path = os.path.join(work_dir, f"beat_{i}_start.png")
    end_path = os.path.join(work_dir, f"beat_{i}_end.png")
    image_gen.generate_image(beat["prompt_start"], start_path)
    image_gen.generate_image(beat["prompt_end"], end_path)
    clip_path = os.path.join(work_dir, f"beat_{i}_clip.mp4")
    video_gen.generate_video_segment(start_path, end_path, beat["duration_sec"], clip_path)
    cost = 2 * _IMAGE_COST_USD + beat["duration_sec"] * _VIDEO_COST_PER_SEC_USD
    return clip_path, cost


def run_pipeline(work_dir: str = "work", state_path: str = "state/history.json") -> dict | None:
    _preflight_check()
    os.makedirs(work_dir, exist_ok=True)
    current_state = state.load_state(state_path)

    idea = ideas.generate_idea(recent=state.recent_combos(current_state))
    board = storyboard.generate_storyboard(idea)

    asset_paths = []
    total_cost = 0.0
    for i, beat in enumerate(board["beats"]):
        path, cost = _generate_beat_asset(i, beat, work_dir)
        asset_paths.append(path)
        total_cost += cost

    music_path = os.path.join(_MUSIC_DIR, music.pick_music(idea["audio_mood"]))
    if not os.path.exists(music_path):
        raise FileNotFoundError(
            f"music track not found: {music_path} "
            "(check assets/music/manifest.json and assets/music/README.md)"
        )
    final_path = os.path.join(work_dir, "final.mp4")
    assemble.assemble_video(board, asset_paths, music_path, final_path, work_dir=work_dir)

    approved = telegram_approval.request_approval(
        final_path, board["title"], board["description"], timeout_sec=_APPROVAL_TIMEOUT_SEC
    )

    video_id = f"{idea['location']}-{board['title']}"[:80]
    state.record_combo(current_state, idea)
    state.record_cost(current_state, video_id, round(total_cost, 2), {"beats": len(board["beats"])})

    youtube_id = None
    if approved:
        youtube_id = youtube_publish.publish_video(
            final_path, board["title"], board["description"], board["tags"],
            contains_synthetic_media=True,
        )
        state.record_published(current_state, video_id, youtube_id, {
            "title": board["title"], "idea": idea,
        })

    state.save_state(current_state, state_path)
    return {"published": approved, "youtube_id": youtube_id, "cost_usd": round(total_cost, 2)}


if __name__ == "__main__":
    result = run_pipeline()
    print(result)
