"""Turns a 5-axis idea into a shot list, captions, and SEO metadata.

The validation here is what keeps the format honest: at least 30 seconds and
all four story beats (spec §4.1). A Short that is 15 seconds of the same shot
is exactly the "low-effort template" YouTube's inauthentic-content policy
targets, so a storyboard that fails validation is regenerated rather than built.
"""

import json
import numbers

from pipeline import llm as llm_module

_REQUIRED_STAGES = {"setup", "progress", "twist", "reveal"}
_VALID_PANS = {"in", "out", "left", "right"}
_MIN_DURATION_SEC = 30

_SYSTEM_PROMPT = (
    "You are a short-form video storyboard writer. Given a 5-axis video concept, produce a "
    "shot list for a vertical AI-generated build video. Respond with ONLY a single valid JSON "
    "object, no markdown fences, with keys: beats (a list), title, description, tags (a list "
    "of strings). Each beat must have: stage (one of setup/progress/twist/reveal), type (one of "
    "transform_video/still_pan), duration_sec (a number), caption (a short on-screen text string). "
    "If type is transform_video, also include prompt_start and prompt_end (image generation "
    "prompts describing the before/after of that shot). If type is still_pan, also include "
    "prompt (an image generation prompt) and pan (one of in/out/left/right). The beats must sum "
    "to at least 30 seconds total and must cover all four stages: setup, progress, twist, reveal."
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

    # Check durations first: a non-numeric duration_sec would otherwise blow up
    # the sum() below with an uncaught TypeError instead of triggering a retry.
    for i, beat in enumerate(beats):
        duration = beat.get("duration_sec")
        if not isinstance(duration, numbers.Real) or isinstance(duration, bool) or duration <= 0:
            raise StoryboardValidationError(
                f"beat {i} has a non-numeric or non-positive duration_sec: {duration!r}"
            )

    total_duration = sum(beat["duration_sec"] for beat in beats)
    if total_duration < _MIN_DURATION_SEC:
        raise StoryboardValidationError(
            f"total duration {total_duration}s is under the required {_MIN_DURATION_SEC}s minimum"
        )

    stages_present = {beat.get("stage") for beat in beats}
    missing = _REQUIRED_STAGES - stages_present
    if missing:
        raise StoryboardValidationError(f"storyboard is missing required stage(s): {sorted(missing)}")

    for i, beat in enumerate(beats):
        if beat.get("type") == "transform_video":
            if not beat.get("prompt_start") or not beat.get("prompt_end"):
                raise StoryboardValidationError(
                    f"beat {i} is transform_video but missing prompt_start/prompt_end"
                )
        elif beat.get("type") == "still_pan":
            if not beat.get("prompt"):
                raise StoryboardValidationError(f"beat {i} is still_pan but missing prompt")
            if beat.get("pan") not in _VALID_PANS:
                raise StoryboardValidationError(
                    f"beat {i} is still_pan with an invalid pan direction: {beat.get('pan')!r}"
                )
        else:
            raise StoryboardValidationError(f"beat {i} has unknown type {beat.get('type')!r}")


def generate_storyboard(idea: dict, call_llm=llm_module.call_llm, max_attempts: int = 3) -> dict:
    prompt = _build_prompt(idea)
    last_error = None
    for _ in range(max_attempts):
        raw = call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=2048)
        try:
            parsed = json.loads(llm_module.strip_json_fences(raw))
            if not isinstance(parsed, dict):
                raise StoryboardValidationError(
                    f"expected a JSON object, got {type(parsed).__name__}"
                )
            validate_storyboard(parsed)
        except (json.JSONDecodeError, StoryboardValidationError) as exc:
            last_error = exc
            continue
        return parsed
    raise StoryboardValidationError(
        f"could not get a valid storyboard after {max_attempts} attempts: {last_error}"
    )
