import os
from pipeline import state, ideas, storyboard, image_gen, video_gen, music, assemble, telegram_approval, youtube_publish

_IMAGE_COST_USD = 0.15
_VIDEO_COST_PER_SEC_USD = 0.02


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

    music_path = music.pick_music(idea["audio_mood"])
    final_path = os.path.join(work_dir, "final.mp4")
    assemble.assemble_video(board, asset_paths, music_path, final_path, work_dir=work_dir)

    approved = telegram_approval.request_approval(final_path, board["title"], board["description"])

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
