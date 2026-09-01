# LLM Gemini Free-Tier Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `src/pipeline/llm.py`'s Anthropic Claude backend with Google Gemini's free tier (via the already-proven Interactions API pattern from `image_gen.py`), and remove Anthropic entirely from the codebase.

**Architecture:** `llm.py` is rewritten to call `https://generativelanguage.googleapis.com/v1beta/interactions` with `requests` instead of the `anthropic` SDK — the exact endpoint, auth header, and `steps[].content[]` response-scanning pattern `image_gen.py` already uses in production. `call_llm`'s public signature and behavior are unchanged, so `ideas.py` and `storyboard.py` require zero edits.

**Tech Stack:** Python 3.11, `requests` (already a dependency — no new package). Removes the `anthropic` package entirely.

## Global Constraints

- `call_llm(prompt: str, system: str | None = None, max_tokens: int = 1024, retries: int = 3) -> str` — signature and behavior (success returns text, exhausted retries raises `LLMError`) must not change.
- `ideas.py` and `storyboard.py` get zero code changes — they only ever import `call_llm`.
- Model comes from `GEMINI_TEXT_MODEL` env var, default `"gemini-flash-latest"` (a Google-maintained alias for the current stable Flash model — free tier eligible, no credit card required).
- Reuse the existing `GEMINI_API_KEY` — no new secret.
- Anthropic is removed completely: the `anthropic` package, `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` env vars, and all mentions in docs/config, per the approved spec and the user's explicit choice (not deprioritized, not left dormant).
- Follow `image_gen.py`'s exact request/auth pattern (`x-goog-api-key` header, not a query param) since that pattern is already verified working in production — do not reintroduce the legacy `models/{id}:generateContent` shape.
- **Note found during planning, correcting the spec's §3.3 cleanup list:** `src/pipeline/orchestrator.py` has no `_REQUIRED_ENV_VARS` / preflight env-check list in the current code on `main` (verified by reading the file — no such list exists). That cleanup item does not apply; skip it. `CLAUDE.md` also has no Anthropic-specific claims to update (verified by search) — only `README.md`, `docs/STATE.md`, `todo.md`, `.env.example`, `requirements.txt`, and `.github/workflows/daily-shorts.yml` need changes.

---

## File Structure

```
D:\shorts\
  src/pipeline/
    llm.py                # rewritten: requests-based Gemini Interactions API client
  tests/
    test_llm.py             # rewritten to match (mocks requests.post, not an SDK client)
  requirements.txt           # anthropic removed
  .env.example                 # ANTHROPIC_API_KEY/ANTHROPIC_MODEL removed, GEMINI_TEXT_MODEL added
  .github/workflows/daily-shorts.yml   # ANTHROPIC_API_KEY secret line removed
  README.md                     # "Anthropic" -> "Gemini" in the module table, secrets list (8 -> 7)
  docs/STATE.md                  # module table entry, "외부 시스템" secret count, Anthropic SDK gotcha section
  todo.md                         # secrets list (8 -> 7)
```

`llm.py` keeps its existing single responsibility ("the only module that talks to Gemini for text generation") — only its transport changes, not its role in the pipeline.

---

## Task 1: Rewrite `llm.py` for the Gemini Interactions API

**Files:**
- Modify: `src/pipeline/llm.py` (full rewrite)
- Test: `tests/test_llm.py` (full rewrite)

**Interfaces:**
- Consumes: `GEMINI_API_KEY` env var (already used by `image_gen.py` — no new secret); `GEMINI_TEXT_MODEL` env var (new, default `"gemini-flash-latest"`).
- Produces: `call_llm(prompt: str, system: str | None = None, max_tokens: int = 1024, retries: int = 3) -> str` (unchanged signature), `LLMError` exception (unchanged name), `strip_json_fences(raw: str) -> str` (unchanged, no logic change — copy forward as-is since it doesn't touch the API). `ideas.py` and `storyboard.py` consume these by these exact names already; do not rename anything.

**Before implementing:** the exact Interactions API field names below (`system_instruction`, `generation_config.max_output_tokens`, `response_format.type: "text"`) were confirmed via live web search during planning (this is a newer, evolving API — it had breaking changes as recently as May 2026), but double-check them against `https://ai.google.dev/api/interactions-api` before finalizing if anything in Step 3/4 fails against a real key later (per `CLAUDE.md`'s standing rule: "외부 API를 건드릴 땐 라이브 문서를 먼저 확인한다"). The `input`/`model`/`response_format`/auth-header parts are not new risk — they're copied verbatim from `image_gen.py`, which is already verified working in production.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/test_llm.py` with:

```python
from unittest.mock import patch, MagicMock

import pytest

from pipeline import llm


def _fake_response(content=None, status_code=200):
    """A Gemini Interactions API response (steps -> model_output -> content)."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = "error body"
    resp.json.return_value = {
        "id": "int_123",
        "status": "completed",
        "steps": [
            {"type": "user_input", "status": "done",
             "content": [{"type": "text", "text": "irrelevant"}]},
            {"type": "model_output", "status": "done",
             "content": content if content is not None else
             [{"type": "text", "text": "hello world"}]},
        ],
    }
    return resp


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@patch("pipeline.llm.requests.post")
def test_call_llm_returns_text_from_the_response(mock_post):
    mock_post.return_value = _fake_response()
    assert llm.call_llm("say hello") == "hello world"


@patch("pipeline.llm.requests.post")
def test_call_llm_skips_non_text_parts_and_finds_the_text_part(mock_post):
    mock_post.return_value = _fake_response(content=[
        {"type": "thought", "text": "hmm, thinking..."},
        {"type": "text", "text": "the answer"},
    ])
    assert llm.call_llm("think then answer") == "the answer"


@patch("pipeline.llm.requests.post")
def test_call_llm_raises_when_response_has_no_text_part(mock_post):
    mock_post.return_value = _fake_response(content=[{"type": "thought", "text": "..."}])
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=1)


@patch("pipeline.llm.requests.post")
def test_call_llm_sends_prompt_and_model_in_request_body(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt")
    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["model"] == llm.MODEL
    assert body["input"] == [{"type": "text", "text": "prompt"}]


@patch("pipeline.llm.requests.post")
def test_call_llm_sends_api_key_as_a_header_not_a_query_param(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt")
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["x-goog-api-key"] == "test-key"
    assert "params" not in kwargs


@patch("pipeline.llm.requests.post")
def test_call_llm_passes_system_prompt_and_max_tokens(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt", system="be terse", max_tokens=50)
    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["system_instruction"] == "be terse"
    assert body["generation_config"]["max_output_tokens"] == 50


@patch("pipeline.llm.requests.post")
def test_call_llm_omits_system_instruction_when_not_given(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt")
    _, kwargs = mock_post.call_args
    assert "system_instruction" not in kwargs["json"]


@patch("pipeline.llm.requests.post")
def test_call_llm_requests_plain_text_output(mock_post):
    mock_post.return_value = _fake_response()
    llm.call_llm("prompt")
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["response_format"] == {"type": "text"}


@patch("pipeline.llm.requests.post")
def test_call_llm_raises_on_non_200(mock_post):
    mock_post.return_value = _fake_response(status_code=400)
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=1)


@patch("pipeline.llm.requests.post")
def test_call_llm_raises_before_calling_the_api_when_key_is_missing(mock_post, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY"):
        llm.call_llm("prompt")
    mock_post.assert_not_called()


@patch("pipeline.llm.requests.post")
def test_call_llm_retries_then_raises_after_exhausting_retries(mock_post):
    mock_post.side_effect = RuntimeError("boom")
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=2)
    assert mock_post.call_count == 2


@patch("pipeline.llm.requests.post")
def test_call_llm_succeeds_on_retry_after_a_transient_failure(mock_post):
    mock_post.side_effect = [RuntimeError("transient"), _fake_response(content=[
        {"type": "text", "text": "recovered"},
    ])]
    assert llm.call_llm("prompt", retries=3) == "recovered"
    assert mock_post.call_count == 2


def test_strip_json_fences_drops_a_json_code_fence():
    raw = '```json\n{"a": 1}\n```'
    assert llm.strip_json_fences(raw) == '{"a": 1}'


def test_strip_json_fences_leaves_unfenced_text_alone():
    assert llm.strip_json_fences('{"a": 1}') == '{"a": 1}'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_llm.py -v`
Expected: every test that references `llm.requests` or the new request/response shape fails — either with `AttributeError: module 'pipeline.llm' has no attribute 'requests'` (since the current module imports `anthropic`, not `requests`) or, once the import itself is patched by `@patch`, with failures from the old Anthropic-shaped implementation not matching the new assertions. The two `strip_json_fences` tests should already pass (that function isn't changing) — confirm they do, so you know the RED failures are isolated to the API-transport change.

- [ ] **Step 3: Rewrite `src/pipeline/llm.py`**

```python
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
    """Find the first text part in the response timeline.

    Mirrors image_gen.py's _extract_image_data: scan steps[].content[] rather
    than index blindly, since the model may emit multiple parts (e.g. a
    thinking part alongside the answer) and step order is not guaranteed.
    """
    for step in payload.get("steps", []):
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_llm.py -v`
Expected: all 14 tests pass.

- [ ] **Step 5: Run the full suite to confirm `ideas.py`/`storyboard.py` still work unmodified**

Run: `export PATH="$PATH:/c/Users/user/ffmpeg/ffmpeg-9.0.1-essentials_build/bin" && python -m pytest -v` (ffmpeg on PATH needed for `tests/test_assemble.py`; adjust the path if it's installed elsewhere on the machine you're running on)
Expected: full suite passes (117 tests before this change — confirm the same count still passes, since `tests/test_ideas.py`/`tests/test_storyboard.py` mock `call_llm` directly by name and should be completely unaffected by this rewrite).

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/llm.py tests/test_llm.py
git commit -m "$(cat <<'EOF'
feat: LLM 백엔드를 Anthropic에서 Gemini 무료 티어로 교체

Anthropic API는 영구 무료 티어가 없어 결제가 필요했다. image_gen.py가 이미
검증한 Gemini Interactions API 패턴을 그대로 재사용해 call_llm을 다시 짰다.
시그니처는 그대로라 ideas.py/storyboard.py는 손대지 않았다.
EOF
)"
```

---

## Task 2: Remove Anthropic from dependencies, env config, and CI

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `.github/workflows/daily-shorts.yml`

**Interfaces:**
- Consumes: Task 1's `GEMINI_TEXT_MODEL` env var name (documented here, not introduced here).
- Produces: nothing consumed by later tasks — this is dependency/config cleanup.

- [ ] **Step 1: Remove `anthropic` from `requirements.txt`**

Current content:
```
anthropic>=0.40.0
requests>=2.32.0
Pillow>=10.4.0
pytest>=8.3.0
```

Change to:
```
requests>=2.32.0
Pillow>=10.4.0
pytest>=8.3.0
```

- [ ] **Step 2: Update `.env.example`**

Replace the current opening block:
```
# Anthropic (idea + storyboard generation)
ANTHROPIC_API_KEY=
# Optional: override the model. Defaults to claude-opus-5.
ANTHROPIC_MODEL=

# Nano Banana Pro / Gemini image generation
GEMINI_API_KEY=
```

With:
```
# Gemini (idea + storyboard generation, via the free tier — and image
# generation, which is paid; see the "Optional tuning" section below for the
# model override for each)
GEMINI_API_KEY=
```

And in the "Optional tuning" section near the bottom of the file (after the existing `CAPTION_FONT=` line and before the `VALIDATION_BUDGET_USD=` block), add:
```
# Idea/storyboard text model (default gemini-flash-latest — the current
# stable Flash model, free tier eligible).
GEMINI_TEXT_MODEL=
```

Verify the rest of the "Optional tuning" section (`APPROVAL_TIMEOUT_SEC`, `MAX_COST_USD`, `CAPTION_FONT`, `VALIDATION_*`) is untouched — only the Anthropic block at the top and the new `GEMINI_TEXT_MODEL` line change.

- [ ] **Step 3: Remove the `ANTHROPIC_API_KEY` secret from the workflow**

In `.github/workflows/daily-shorts.yml`, the "Run daily pipeline" step's `env:` block currently starts:
```yaml
        env:
          # The package lives in src/. pytest.ini's `pythonpath = src` applies
          # to pytest only, so `python -m pipeline.orchestrator` needs this or
          # it dies with ModuleNotFoundError before doing anything at all.
          PYTHONPATH: src
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

Remove the `ANTHROPIC_API_KEY` line:
```yaml
        env:
          # The package lives in src/. pytest.ini's `pythonpath = src` applies
          # to pytest only, so `python -m pipeline.orchestrator` needs this or
          # it dies with ModuleNotFoundError before doing anything at all.
          PYTHONPATH: src
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

Leave every other line in that `env:` block (`MINIMAX_API_KEY` through `VALIDATION_ACK_COUNT`) unchanged.

- [ ] **Step 4: Verify the workflow YAML is still valid**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-shorts.yml', encoding='utf-8'))"`
Expected: no output, no error.

- [ ] **Step 5: Verify the new requirements install cleanly**

Run: `python -m pip install -r requirements.txt`
Expected: succeeds with no errors (this also effectively uninstalls nothing — `pip install` doesn't remove already-installed packages not listed — but confirms the trimmed file itself is well-formed and resolvable).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .github/workflows/daily-shorts.yml
git commit -m "$(cat <<'EOF'
chore: Anthropic 의존성·시크릿·환경변수 예시 제거

llm.py가 더 이상 anthropic 패키지를 쓰지 않는다. requirements.txt에서 빼고,
.env.example의 ANTHROPIC_API_KEY/ANTHROPIC_MODEL을 GEMINI_TEXT_MODEL로
대체했다. 워크플로의 ANTHROPIC_API_KEY 시크릿 참조도 제거.
EOF
)"
```

---

## Task 3: Update hand-off docs

**Files:**
- Modify: `README.md`
- Modify: `docs/STATE.md`
- Modify: `todo.md`

**Interfaces:**
- Consumes: nothing (pure documentation).
- Produces: nothing consumed elsewhere — this is the last task.

- [ ] **Step 1: Update `README.md`**

Find this sentence (module-responsibility paragraph):
```
각 모듈은 하나씩만 담당한다. `state.py`는 네트워크를 모르고, `llm.py`만 Anthropic을
호출하며, `assemble.py`는 ffmpeg만 돌린다. `orchestrator.py`에는 자체 로직이 없다 —
```
Change `` `llm.py`만 Anthropic을 호출하며 `` to `` `llm.py`만 Gemini를 호출해 텍스트를 생성하며 ``.

Find the secrets list (currently 8 items starting with `ANTHROPIC_API_KEY`):
```
   `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MINIMAX_API_KEY`,
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
```
Remove `` `ANTHROPIC_API_KEY`, `` so it reads:
```
   `GEMINI_API_KEY`, `MINIMAX_API_KEY`,
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
```

- [ ] **Step 2: Update `docs/STATE.md`**

Read the file fresh first (it changes between sessions — don't assume the excerpts below are still at the same line numbers).

Find the module table row:
```
| `llm.py` | Anthropic 호출은 여기서만. 재시도 + JSON 펜스 제거 |
```
Change to:
```
| `llm.py` | Gemini 호출은 여기서만 (텍스트 생성, 무료 티어). 재시도 + JSON 펜스 제거 |
```

Find and remove the Anthropic-specific "최근에 알게 된 것" entry (the block starting "**Anthropic SDK: `response.content[0].text`는 버그다.**" and continuing through the `ANTHROPIC_MODEL=claude-sonnet-5` line) — this entire gotcha no longer applies since the SDK is gone. Delete that block entirely (do not leave an empty heading behind — if it was the only item under its subheading, remove the now-empty subheading too; if other unrelated gotchas share the same subsection, keep the subsection and just remove this one entry).

Find the "외부 시스템" section's line mentioning API key count:
```
- **API 키 4종(Anthropic/Gemini/MiniMax/Telegram): 발급 여부 미확인.**
```
Update to reflect 3 keys (Anthropic removed) — check the current state of this line first, since `assets/music/` and Telegram bot setup may already be marked done elsewhere in the file from prior sessions; only change the API-key-count wording, don't rewrite unrelated parts of this line if it's already been edited since this plan was written.

- [ ] **Step 3: Update `todo.md`**

Read the file fresh first (same caveat as Step 2).

Find the secrets list (likely still 8 items, matching README's original list):
```
  `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MINIMAX_API_KEY`,
```
Remove `` `ANTHROPIC_API_KEY`, `` from that line, matching the same edit made to `README.md` in Step 1.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/STATE.md todo.md
git commit -m "$(cat <<'EOF'
docs: LLM 제공자 교체(Gemini) 반영 — Anthropic 관련 서술 정리

README/STATE.md/todo.md의 Anthropic 언급을 제거하거나 Gemini로 갱신했다.
시크릿 목록도 8종에서 7종으로.
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** §3.1(llm.py 재작성)→Task 1, §3.2(인터페이스 유지)→Task 1 (verified by not touching ideas.py/storyboard.py at all, and Task 1 Step 5 explicitly re-runs the full suite to confirm), §3.3(Anthropic 완전 제거)→Tasks 2-3 (with one correction: orchestrator.py's `_REQUIRED_ENV_VARS` does not exist on current `main`, noted in Global Constraints), §4(테스트)→Task 1's rewritten `tests/test_llm.py` mirrors `tests/test_image_gen.py`'s style as specified, §5(범위 밖: JSON 스키마 출력, 이미지 생성 교체)→neither appears anywhere in this plan.
- **Placeholder scan:** none — every step has literal code, exact before/after text for doc edits, and exact commands with expected output. Task 3's doc edits explicitly instruct reading the file fresh first (since these are living documents) rather than assuming stale line numbers, which is guidance, not a placeholder — the actual find/replace text given is concrete and exact.
- **Type consistency:** `call_llm`/`LLMError`/`strip_json_fences`/`MODEL`/`ENDPOINT` names in Task 1's implementation match exactly what its own tests reference (`llm.call_llm`, `llm.LLMError`, `llm.strip_json_fences`, `llm.MODEL`) — no other task references `llm.py`'s internals, since `ideas.py`/`storyboard.py` only ever call `call_llm` (confirmed unchanged, not touched by this plan).
