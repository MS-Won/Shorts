"""The only module that talks to Gemini for text generation.

`ideas.py` and `storyboard.py` both go through `call_llm` so that the model
choice, retry policy, and response-parsing rules live in exactly one place.
"""

import os
import time

import requests

# "gemini-flash-latest" always points at the current stable Flash model, which
# has a permanent free tier (spec: 2026-09-01-llm-gemini-free-tier-design.md)
# — overridable so a run can be pinned to a specific model without touching code.
MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-latest")

# Same Interactions API endpoint image_gen.py already uses in production — do
# not switch to the legacy models/{id}:generateContent shape (see its module
# docstring for why).
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"


class LLMError(Exception):
    pass


def strip_json_fences(raw: str) -> str:
    """Drop a ```json ... ``` wrapper if the model added one anyway.

    Every JSON-producing prompt in this pipeline forbids fences, and the model
    mostly obeys — but not always. Fixing it here is far cheaper than burning a
    retry (and another paid API call) on output that is otherwise valid JSON.
    """
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    if lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines[1:]).strip()


def _extract_text(payload: dict) -> str:
    """Find the first text part in the model_output step.

    Mirrors image_gen.py's _extract_image_data: scan steps[].content[] rather
    than index blindly, since the model may emit multiple parts (e.g. a
    thinking part alongside the answer) and step order is not guaranteed.
    """
    for step in payload.get("steps", []):
        if step.get("type") == "model_output":
            for item in step.get("content", []) or []:
                if item.get("type") == "text" and item.get("text"):
                    return item["text"]
    raise LLMError(f"no text found in response: {payload}")


def call_llm(prompt: str, system: str | None = None, max_tokens: int = 1024, retries: int = 3) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise LLMError("GEMINI_API_KEY is not set")

    body = {
        "model": MODEL,
        "input": [{"type": "text", "text": prompt}],
        "response_format": {"type": "text"},
        "generation_config": {"max_output_tokens": max_tokens},
    }
    if system is not None:
        body["system_instruction"] = system

    last_error = None
    for attempt in range(retries):
        try:
            response = requests.post(
                ENDPOINT,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=body,
                timeout=120,
            )
            if response.status_code != 200:
                raise LLMError(f"LLM call failed ({response.status_code}): {response.text}")
            return _extract_text(response.json())
        except Exception as exc:  # noqa: BLE001 - any network/parsing error should trigger a retry
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise LLMError(f"LLM call failed after {retries} attempts: {last_error}")
