import os
import time
import anthropic

_MODEL = "claude-sonnet-5"
_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


class LLMError(Exception):
    pass


def call_llm(prompt: str, system: str | None = None, max_tokens: int = 1024, retries: int = 3) -> str:
    last_error = None
    for attempt in range(retries):
        try:
            kwargs = {
                "model": _MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system is not None:
                kwargs["system"] = system
            response = _client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as exc:  # noqa: BLE001 - any SDK/network error should trigger a retry
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise LLMError(f"LLM call failed after {retries} attempts: {last_error}")
