"""Wires the whole daily run together.

Deliberately contains no business logic of its own — it decides order, money,
and what gets written to state, and delegates everything else.
"""

import os
import uuid
from datetime import datetime, timezone

from pipeline import (
    assemble,
    ideas,
    image_gen,
    music,
    state,
    storyboard,
    telegram_approval,
    video_gen,
    youtube_publish,
)

IMAGE_COST_USD = 0.15
VIDEO_COST_PER_SEC_USD = 0.02

# Spec §5 puts the target raw cost at $3-5 per video. Nothing else in the
# pipeline bounds spend: the storyboard only has to be *at least* 30 seconds,
# so a model that gets enthusiastic about transform beats can quietly triple
# the bill. The estimate is checked before a single paid call is made.
MAX_COST_USD = float(os.environ.get("MAX_COST_USD", "5.0"))
MAX_STORYBOARD_ATTEMPTS = 3


def _env_float(name: str, default: float) -> float:
    # GitHub Actions' `vars.X` resolves to "" (not "unset") when the
    # repository Variable doesn't exist, so an empty string must fall back
    # to the default rather than crash `float("")`.
    raw = os.environ.get(name, "")
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    return int(raw) if raw else default


# The niche's revenue is unproven — these bound how much gets spent finding
# out. Both checks read the existing cost_log in state/history.json, so no
# state schema change is needed. VALIDATION_ACK_COUNT is the one value a
# human moves by hand, and moving it *is* the record that a checkpoint was
# reviewed — see docs/superpowers/specs/2026-09-01-validation-budget-guard-design.md.
VALIDATION_BUDGET_USD = _env_float("VALIDATION_BUDGET_USD", 125.0)
VALIDATION_CHECKPOINT_EVERY = _env_int("VALIDATION_CHECKPOINT_EVERY", 10)
VALIDATION_ACK_COUNT = _env_int("VALIDATION_ACK_COUNT", 0)


def estimate_cost(board: dict) -> float:
    """What this storyboard will cost to generate, before generating it."""
    total = 0.0
    for beat in board["beats"]:
        if beat["type"] == "still_pan":
            total += IMAGE_COST_USD
        else:
            total += 2 * IMAGE_COST_USD + beat["duration_sec"] * VIDEO_COST_PER_SEC_USD
    return total


def _make_video_id(idea: dict, board: dict) -> str:
    """Unique per run — the cost log is keyed on it, and ideas can recur."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def _motion_prompt(beat: dict) -> str:
    return f"{beat['prompt_start']} transforming into {beat['prompt_end']}"


def _generate_beat_asset(i: int, beat: dict, work_dir: str) -> tuple[str, float]:
    if beat["type"] == "still_pan":
        path = os.path.join(work_dir, f"beat_{i}_still.png")
        image_gen.generate_image(beat["prompt"], path)
        return path, IMAGE_COST_USD

    start_path = os.path.join(work_dir, f"beat_{i}_start.png")
    end_path = os.path.join(work_dir, f"beat_{i}_end.png")
    image_gen.generate_image(beat["prompt_start"], start_path)
    image_gen.generate_image(beat["prompt_end"], end_path)

    clip_path = os.path.join(work_dir, f"beat_{i}_clip.mp4")
    video_gen.generate_video_segment(start_path, end_path, beat["duration_sec"], clip_path,
                                     prompt=_motion_prompt(beat))
    cost = 2 * IMAGE_COST_USD + beat["duration_sec"] * VIDEO_COST_PER_SEC_USD
    return clip_path, cost


def _affordable_storyboard(idea: dict) -> dict | None:
    """Generate storyboards until one fits the budget, or give up."""
    for _ in range(MAX_STORYBOARD_ATTEMPTS):
        board = storyboard.generate_storyboard(idea)
        if estimate_cost(board) <= MAX_COST_USD:
            return board
    return None


def _validation_guard(current_state: dict) -> str | None:
    """A reason to stop before spending anything, or None to proceed.

    Enforcement only — deciding whether the numbers justify continuing is a
    person's job, not this function's.
    """
    spent = sum(entry["cost_usd"] for entry in current_state["cost_log"])
    if spent >= VALIDATION_BUDGET_USD:
        return (
            f"검증 예산 소진: ${spent:.2f} / ${VALIDATION_BUDGET_USD:.2f}. "
            "계속하려면 VALIDATION_BUDGET_USD를 올리거나 여기서 중단하세요."
        )

    made = len(current_state["cost_log"])
    if made >= VALIDATION_ACK_COUNT + VALIDATION_CHECKPOINT_EVERY:
        return (
            f"체크포인트 도달: 영상 {made}편, 누적 ${spent:.2f} 지출. "
            f"YouTube Studio 확인 후 계속하려면 VALIDATION_ACK_COUNT를 {made}(으)로 올리세요."
        )

    return None


def run_pipeline(work_dir: str = "work", state_path: str = "state/history.json") -> dict | None:
    os.makedirs(work_dir, exist_ok=True)
    current_state = state.load_state(state_path)

    blocked = _validation_guard(current_state)
    if blocked is not None:
        telegram_approval.notify(blocked)
        print(f"::warning::pipeline aborted before spending anything: {blocked}")
        return None

    try:
        idea = ideas.generate_idea(recent=state.recent_combos(current_state))
        board = _affordable_storyboard(idea)
    except (ideas.IdeaGenerationError, storyboard.StoryboardValidationError) as exc:
        print(f"pipeline aborted before spending anything: {exc}")
        return None

    if board is None:
        print(
            f"pipeline aborted: no storyboard came in under the ${MAX_COST_USD:.2f} budget "
            f"in {MAX_STORYBOARD_ATTEMPTS} attempts"
        )
        return None

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

    # Recorded whether or not it ships: the money is spent either way, and the
    # idea must not come back around tomorrow.
    video_id = _make_video_id(idea, board)
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
    print(run_pipeline())
