"""The only module that talks to Anthropic.

`ideas.py` and `storyboard.py` both go through `call_llm` so that the model
choice, retry policy, and response-parsing rules live in exactly one place.
"""

import os
import time

import anthropic

# Overridable so a run can be pinned to a cheaper model without touching code.
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


class LLMError(Exception):
    pass


def _first_text(response) -> str:
    """Return the first text block's text.

    Not `content[0].text`: thinking is on by default on every current Claude
    model, so the first block is frequently a ThinkingBlock, which carries
    `.thinking` and has no `.text` at all.
    """
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise LLMError("response contained no text block")


def call_llm(prompt: str, system: str | None = None, max_tokens: int = 1024, retries: int = 3) -> str:
    last_error = None
    for attempt in range(retries):
        try:
            kwargs = {
                "model": MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system is not None:
                kwargs["system"] = system
            response = _client.messages.create(**kwargs)
            return _first_text(response)
        except Exception as exc:  # noqa: BLE001 - any SDK/network error should trigger a retry
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise LLMError(f"LLM call failed after {retries} attempts: {last_error}")
