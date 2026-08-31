import json
from pipeline import llm as llm_module

_REQUIRED_KEYS = {"location", "concept", "hook", "visual_style", "audio_mood"}

_SYSTEM_PROMPT = (
    "You are a viral short-form video concept writer for a channel about AI-imagined "
    "house builds in unusual real-world locations (school buses, warehouses, volcanoes, "
    "ice caves, etc). You must invent a genuinely new combination each time — never repeat "
    "a past idea. Respond with ONLY a single valid JSON object, no other text, no markdown "
    "fences, with exactly these keys: location, concept, hook, visual_style, audio_mood."
)


class IdeaGenerationError(Exception):
    pass


def _build_prompt(recent: list[dict]) -> str:
    if not recent:
        recent_text = "(no past ideas yet)"
    else:
        recent_text = "\n".join(
            f"- location={c.get('location')}, concept={c.get('concept')}, hook={c.get('hook')}"
            for c in recent
        )
    return (
        "Here are the most recent ideas already used, avoid repeating or closely resembling "
        f"any of them:\n{recent_text}\n\n"
        "Generate one brand-new idea now as a JSON object with keys: "
        "location, concept, hook, visual_style, audio_mood."
    )


def generate_idea(recent: list[dict], call_llm=llm_module.call_llm, max_attempts: int = 3) -> dict:
    prompt = _build_prompt(recent)
    last_error = None
    for _ in range(max_attempts):
        raw = call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=512)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not _REQUIRED_KEYS.issubset(parsed.keys()):
            last_error = ValueError(f"missing keys, got {list(parsed.keys())}")
            continue
        return {key: parsed[key] for key in _REQUIRED_KEYS}
    raise IdeaGenerationError(f"could not get a valid idea after {max_attempts} attempts: {last_error}")
