import json
from pipeline import llm as llm_module

_REQUIRED_STAGES = {"setup", "progress", "twist", "reveal"}
_MIN_DURATION_SEC = 30
_MAX_DURATION_SEC = 60
_MAX_BEATS = 10
_VALID_TRANSFORM_DURATIONS = {5, 10}

_SYSTEM_PROMPT = (
    "You are a short-form video storyboard writer. Given a 5-axis video concept, produce a "
    "shot list for a vertical AI-generated build video. Respond with ONLY a single valid JSON "
    "object, no markdown fences, with keys: beats (a list), title, description, tags (a list "
    "of strings). Each beat must have: stage (one of setup/progress/twist/reveal), type (one of "
    "transform_video/still_pan), duration_sec (a number), caption (a short on-screen text string). "
    "If type is transform_video, also include prompt_start and prompt_end (image generation "
    "prompts describing the before/after of that shot); transform_video beats must use "
    "duration_sec of exactly 5 or 10, no other value. If type is still_pan, also include "
    "prompt (an image generation prompt) and pan (one of in/out/left/right). The beats must sum "
    "to at least 30 seconds and at most 60 seconds total, must use no more than 10 beats, and "
    "must cover all four stages: setup, progress, twist, reveal."
)


class StoryboardValidationError(Exception):
    pass


def _build_prompt(idea: dict) -> str:
    return (
        f"Location: {idea['location']}\n"
        f"Concept: {idea['concept']}\n"
        f"Hook/twist: {idea['hook']}\n"
        f"Visual style: {idea['visual_style']}\n"
        f"Audio mood: {idea['audio_mood']}\n\n"
        "Write the storyboard now as a JSON object."
    )


def validate_storyboard(storyboard: dict) -> None:
    beats = storyboard.get("beats", [])
    total_duration = sum(b.get("duration_sec", 0) for b in beats)
    if total_duration < _MIN_DURATION_SEC:
        raise StoryboardValidationError(
            f"total duration {total_duration}s is under the required {_MIN_DURATION_SEC}s minimum"
        )
    if total_duration > _MAX_DURATION_SEC:
        raise StoryboardValidationError(
            f"total duration {total_duration}s exceeds the {_MAX_DURATION_SEC}s maximum"
        )
    if len(beats) > _MAX_BEATS:
        raise StoryboardValidationError(
            f"storyboard has {len(beats)} beats, exceeding the {_MAX_BEATS} beat maximum"
        )
    stages_present = {b.get("stage") for b in beats}
    missing = _REQUIRED_STAGES - stages_present
    if missing:
        raise StoryboardValidationError(f"storyboard is missing required stage(s): {sorted(missing)}")
    for i, b in enumerate(beats):
        if b.get("type") == "transform_video":
            if not b.get("prompt_start") or not b.get("prompt_end"):
                raise StoryboardValidationError(f"beat {i} is transform_video but missing prompt_start/prompt_end")
            if b.get("duration_sec") not in _VALID_TRANSFORM_DURATIONS:
                raise StoryboardValidationError(
                    f"beat {i} is transform_video with duration_sec={b.get('duration_sec')!r}; "
                    f"must be one of {sorted(_VALID_TRANSFORM_DURATIONS)}"
                )
        elif b.get("type") == "still_pan":
            if not b.get("prompt") or b.get("pan") not in {"in", "out", "left", "right"}:
                raise StoryboardValidationError(f"beat {i} is still_pan but missing prompt or valid pan")
        else:
            raise StoryboardValidationError(f"beat {i} has unknown type {b.get('type')!r}")


def generate_storyboard(idea: dict, call_llm=llm_module.call_llm, max_attempts: int = 3) -> dict:
    prompt = _build_prompt(idea)
    last_error = None
    for _ in range(max_attempts):
        raw = call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=2048)
        try:
            parsed = json.loads(raw)
            validate_storyboard(parsed)
        except (json.JSONDecodeError, StoryboardValidationError) as exc:
            last_error = exc
            continue
        return parsed
    raise StoryboardValidationError(f"could not get a valid storyboard after {max_attempts} attempts: {last_error}")
