# AI Shorts Content Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1 daily-automated pipeline that generates one "AI house-build-in-unusual-location" YouTube Short, gets human approval via Telegram, and publishes it — matching `docs/superpowers/specs/2026-08-31-ai-shorts-content-pipeline-design.md`.

**Architecture:** A Python package (`src/pipeline/`) of small single-purpose modules (state, idea generation, storyboard generation, image/video asset generation, ffmpeg assembly, Telegram approval, YouTube publish) wired together by one orchestrator script. A GitHub Actions workflow runs the orchestrator daily, injecting API keys from Actions Secrets, and commits the updated state file back to the repo.

**Tech Stack:** Python 3.11+, `anthropic` SDK (idea/storyboard generation via Claude), `requests` (all other HTTP: image gen, video gen, Telegram, YouTube), `Pillow` (test fixture images), `pytest`, `ffmpeg`/`ffprobe` (system binaries, called via `subprocess`), GitHub Actions (`ubuntu-latest`).

## Global Constraints

- Shorts must be **30 seconds or longer**, with at least 4 story beats covering stages `setup`, `progress`, `twist`, `reveal` (spec §4.1, §5).
- Target raw generation cost: **$3–5 per video** (spec §5) — achieved via cheap video model (Hailuo-family, ~$0.01–0.03/sec) for transformation beats only, still-image Ken Burns pans for the rest.
- Every video must carry the 5-axis idea (`location`, `concept`, `hook`, `visual_style`, `audio_mood`), freshly generated per run and checked against history to avoid repeats (spec §4.2).
- No TTS/voice narration in v1 — captions are burned-in text only (spec §4.1).
- Every published video must have the YouTube "Altered or synthetic content" disclosure enabled (spec §3.3, §5).
- A human must approve via Telegram before anything publishes; on timeout or rejection, discard and do not publish (spec §5 step ⑤).
- Runs once daily via GitHub Actions; no persistent VM (spec §6). API keys live only in GitHub Actions Secrets, never committed.
- State (used idea combos, per-video cost, published video IDs) persists as JSON committed back to the repo (spec §5 step ⑦).
- Target platform: YouTube Shorts only, new channel (spec §7).

---

## File Structure

```
D:\shorts\
  src/pipeline/
    __init__.py
    llm.py                 # Claude wrapper used by ideas.py and storyboard.py
    state.py                # history.json read/write/query helpers
    ideas.py                 # 5-axis idea generator
    storyboard.py             # shot list + captions + SEO metadata generator
    music.py                   # picks a local royalty-free track by mood
    image_gen.py                # Nano Banana Pro (Gemini image) client
    video_gen.py                  # Hailuo first-last-frame video client
    assemble.py                    # ffmpeg assembly (clips + Ken Burns + captions + music)
    telegram_approval.py            # sends preview, waits for 1-tap approve/reject
    youtube_publish.py               # uploads with synthetic-media disclosure + SEO
    orchestrator.py                   # wires all of the above into one daily run
  assets/music/
    manifest.json            # {mood: [{"file": "...", "attribution": "..."}]}
    README.md                 # manual step: how to populate this folder
  state/
    history.json               # created empty by Task 2's init step
  tests/
    test_state.py
    test_ideas.py
    test_storyboard.py
    test_music.py
    test_image_gen.py
    test_video_gen.py
    test_assemble.py
    test_telegram_approval.py
    test_youtube_publish.py
    test_orchestrator.py
  .github/workflows/daily-shorts.yml
  requirements.txt
  .env.example
  pytest.ini
  .gitignore
```

Each module has exactly one job: `state.py` never talks to a network, `llm.py` is the only file that calls Anthropic, `image_gen.py`/`video_gen.py` are the only files that talk to the AI media APIs, `assemble.py` never makes network calls (pure ffmpeg/subprocess), `telegram_approval.py` and `youtube_publish.py` each own exactly one external integration. `orchestrator.py` contains no business logic of its own — it only calls the other modules in order.

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `src/pipeline/__init__.py`
- Create: `state/history.json`
- Test: none (scaffolding task; verified by running pytest with zero tests collected)

**Interfaces:**
- Produces: the `src/pipeline` package that every later task imports from; the `state/history.json` file that Task 2 reads/writes; the `requirements.txt` every later task's dependencies get added to.

- [x] **Step 1: Verify prerequisites are installed**

Run: `python --version && ffmpeg -version && ffprobe -version`
Expected: Python 3.11+ prints a version; `ffmpeg`/`ffprobe` each print a version banner. If ffmpeg/ffprobe are missing, install them (e.g. `winget install Gyan.FFmpeg` on Windows, or `sudo apt-get install -y ffmpeg` on the GitHub Actions Ubuntu runner — that install happens in Task 13's workflow file, not here) before continuing.

- [x] **Step 2: Create `requirements.txt`**

```
anthropic>=0.40.0
requests>=2.32.0
Pillow>=10.4.0
pytest>=8.3.0
```

- [x] **Step 3: Install dependencies**

Run: `python -m pip install -r requirements.txt`
Expected: all four packages install without error.

- [x] **Step 4: Create `.env.example`**

```
# Anthropic (idea + storyboard generation)
ANTHROPIC_API_KEY=

# Nano Banana Pro / Gemini image generation
GEMINI_API_KEY=

# Hailuo / MiniMax video generation
MINIMAX_API_KEY=

# Telegram approval bot
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# YouTube Data API (OAuth refresh token flow)
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=
```

- [x] **Step 5: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
work/
*.mp4
*.png
!assets/music/**
.pytest_cache/
```

- [x] **Step 6: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = src
```

- [x] **Step 7: Create the package init file**

`src/pipeline/__init__.py`:
```python
```
(empty file — just marks `pipeline` as a package)

- [x] **Step 8: Create the initial empty state file**

`state/history.json`:
```json
{
  "used_combos": [],
  "cost_log": [],
  "published": []
}
```

- [x] **Step 9: Verify pytest runs cleanly with zero tests**

Run: `python -m pytest`
Expected: `no tests ran` (exit code 5) or `collected 0 items` — no import errors.

- [x] **Step 10: Commit**

```bash
git add requirements.txt .env.example .gitignore pytest.ini src/pipeline/__init__.py state/history.json
git commit -m "chore: scaffold pipeline package, deps, and empty state file"
```

---

## Task 2: State Persistence Module

**Files:**
- Create: `src/pipeline/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing (pure file I/O on `state/history.json`).
- Produces:
  - `load_state(path: str = "state/history.json") -> dict`
  - `save_state(state: dict, path: str = "state/history.json") -> None`
  - `record_combo(state: dict, combo: dict) -> None`
  - `recent_combos(state: dict, n: int = 20) -> list[dict]`
  - `record_cost(state: dict, video_id: str, cost_usd: float, breakdown: dict) -> None`
  - `record_published(state: dict, video_id: str, youtube_id: str, metadata: dict) -> None`

  Every later task that touches state uses exactly these six function names and signatures.

- [x] **Step 1: Write the failing tests**

`tests/test_state.py`:
```python
import json
import os
from pipeline import state


def test_load_state_returns_default_shape_when_file_missing(tmp_path):
    path = tmp_path / "history.json"
    result = state.load_state(str(path))
    assert result == {"used_combos": [], "cost_log": [], "published": []}


def test_save_then_load_roundtrips(tmp_path):
    path = tmp_path / "history.json"
    data = {"used_combos": [{"location": "school bus"}], "cost_log": [], "published": []}
    state.save_state(data, str(path))
    assert json.loads(path.read_text()) == data
    assert state.load_state(str(path)) == data


def test_record_combo_appends_with_timestamp():
    s = {"used_combos": [], "cost_log": [], "published": []}
    combo = {"location": "amazon warehouse", "concept": "luxury", "hook": "hidden room",
              "visual_style": "photoreal", "audio_mood": "upbeat"}
    state.record_combo(s, combo)
    assert len(s["used_combos"]) == 1
    assert s["used_combos"][0]["location"] == "amazon warehouse"
    assert "recorded_at" in s["used_combos"][0]


def test_recent_combos_returns_last_n_most_recent_first():
    s = {"used_combos": [], "cost_log": [], "published": []}
    for i in range(5):
        state.record_combo(s, {"location": f"place-{i}"})
    result = state.recent_combos(s, n=2)
    assert [c["location"] for c in result] == ["place-4", "place-3"]


def test_record_cost_appends_entry():
    s = {"used_combos": [], "cost_log": [], "published": []}
    state.record_cost(s, "vid-1", 3.75, {"images": 1.2, "video": 2.55})
    assert s["cost_log"] == [{"video_id": "vid-1", "cost_usd": 3.75,
                                "breakdown": {"images": 1.2, "video": 2.55}}]


def test_record_published_appends_entry():
    s = {"used_combos": [], "cost_log": [], "published": []}
    state.record_published(s, "vid-1", "yt-abc123", {"title": "Built inside a school bus"})
    assert s["published"] == [{"video_id": "vid-1", "youtube_id": "yt-abc123",
                                 "metadata": {"title": "Built inside a school bus"}}]
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_state.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.state'` (or import error) on every test.

- [x] **Step 3: Implement `src/pipeline/state.py`**

```python
import json
import os
from datetime import datetime, timezone


def load_state(path: str = "state/history.json") -> dict:
    if not os.path.exists(path):
        return {"used_combos": [], "cost_log": [], "published": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, path: str = "state/history.json") -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def record_combo(state: dict, combo: dict) -> None:
    entry = dict(combo)
    entry["recorded_at"] = datetime.now(timezone.utc).isoformat()
    state["used_combos"].append(entry)


def recent_combos(state: dict, n: int = 20) -> list[dict]:
    return list(reversed(state["used_combos"][-n:]))


def record_cost(state: dict, video_id: str, cost_usd: float, breakdown: dict) -> None:
    state["cost_log"].append({
        "video_id": video_id,
        "cost_usd": cost_usd,
        "breakdown": breakdown,
    })


def record_published(state: dict, video_id: str, youtube_id: str, metadata: dict) -> None:
    state["published"].append({
        "video_id": video_id,
        "youtube_id": youtube_id,
        "metadata": metadata,
    })
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_state.py -v`
Expected: 6 passed.

- [x] **Step 5: Commit**

```bash
git add src/pipeline/state.py tests/test_state.py
git commit -m "feat: add state persistence module"
```

---

## Task 3: LLM Wrapper

**Files:**
- Create: `src/pipeline/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `ANTHROPIC_API_KEY` env var.
- Produces: `call_llm(prompt: str, system: str | None = None, max_tokens: int = 1024, retries: int = 3) -> str`. Every module that needs LLM output (Task 4, Task 5) imports this exact function.

- [x] **Step 1: Write the failing tests**

`tests/test_llm.py`:
```python
from unittest.mock import patch, MagicMock
import pytest
from pipeline import llm


def _fake_response(text):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


@patch("pipeline.llm._client")
def test_call_llm_returns_text_from_first_content_block(mock_client):
    mock_client.messages.create.return_value = _fake_response("hello world")
    result = llm.call_llm("say hello")
    assert result == "hello world"


@patch("pipeline.llm._client")
def test_call_llm_passes_system_prompt_and_max_tokens(mock_client):
    mock_client.messages.create.return_value = _fake_response("ok")
    llm.call_llm("prompt", system="be terse", max_tokens=50)
    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["system"] == "be terse"
    assert kwargs["max_tokens"] == 50
    assert kwargs["messages"] == [{"role": "user", "content": "prompt"}]


@patch("pipeline.llm._client")
def test_call_llm_retries_then_raises_after_exhausting_retries(mock_client):
    mock_client.messages.create.side_effect = RuntimeError("boom")
    with pytest.raises(llm.LLMError):
        llm.call_llm("prompt", retries=2)
    assert mock_client.messages.create.call_count == 2
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_llm.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.llm'`.

- [x] **Step 3: Implement `src/pipeline/llm.py`**

```python
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
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_llm.py -v`
Expected: 3 passed. (The retry test will sleep ~2s for the backoff between attempt 1 and 2 — acceptable for a unit test; do not add real delay beyond that.)

- [x] **Step 5: Commit**

```bash
git add src/pipeline/llm.py tests/test_llm.py
git commit -m "feat: add Claude LLM wrapper with retry"
```

> **구현 시 계획과 다르게 한 점 (Task 3):**
> 1. 모델을 `claude-sonnet-5` → `claude-opus-5`로 바꾸고 `ANTHROPIC_MODEL`로 덮어쓸 수 있게 했다.
>    영상당 LLM 비용 차이는 약 $0.04로 $3~5 예산에서 무시할 수준인 반면, 아이디어·스토리보드
>    품질은 이 채널이 "AI slop" 판정을 피하는 유일한 방어선이다(스펙 3.3절).
> 2. `response.content[0].text` → 첫 번째 **text 블록**을 찾아 반환하도록 고쳤다.
>    현행 Claude 모델은 thinking이 기본 on이라 `content[0]`이 ThinkingBlock인 경우가 흔한데,
>    ThinkingBlock에는 `.text`가 없어 AttributeError가 나고 그게 재시도 루프에 삼켜져
>    LLMError로 둔갑한다. 텍스트 블록이 아예 없으면 명시적으로 LLMError를 던진다.

---

## Task 4: Idea/Variation Generator (5-Axis System)

**Files:**
- Create: `src/pipeline/ideas.py`
- Test: `tests/test_ideas.py`

**Interfaces:**
- Consumes: `pipeline.llm.call_llm(prompt, system=None, max_tokens=..., retries=...) -> str`; `pipeline.state.recent_combos(state, n) -> list[dict]`.
- Produces: `generate_idea(recent: list[dict], call_llm=llm.call_llm) -> dict` returning exactly the keys `location`, `concept`, `hook`, `visual_style`, `audio_mood`. Task 5 (storyboard) consumes this dict shape directly.

- [x] **Step 1: Write the failing tests**

`tests/test_ideas.py`:
```python
import json
import pytest
from pipeline import ideas


VALID_IDEA_JSON = json.dumps({
    "location": "inside a school bus",
    "concept": "post-apocalyptic bunker",
    "hook": "hidden room behind the driver's seat",
    "visual_style": "photorealistic",
    "audio_mood": "tense and driving",
})


def test_generate_idea_returns_parsed_five_axis_dict():
    def fake_llm(prompt, **kwargs):
        return VALID_IDEA_JSON

    result = ideas.generate_idea(recent=[], call_llm=fake_llm)
    assert set(result.keys()) == {"location", "concept", "hook", "visual_style", "audio_mood"}
    assert result["location"] == "inside a school bus"


def test_generate_idea_includes_recent_combos_in_prompt_to_avoid_repeats():
    captured = {}

    def fake_llm(prompt, **kwargs):
        captured["prompt"] = prompt
        return VALID_IDEA_JSON

    recent = [{"location": "amazon warehouse", "concept": "luxury", "hook": "x",
               "visual_style": "y", "audio_mood": "z"}]
    ideas.generate_idea(recent=recent, call_llm=fake_llm)
    assert "amazon warehouse" in captured["prompt"]


def test_generate_idea_retries_on_invalid_json_then_succeeds():
    calls = {"count": 0}

    def fake_llm(prompt, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return "not json"
        return VALID_IDEA_JSON

    result = ideas.generate_idea(recent=[], call_llm=fake_llm)
    assert result["concept"] == "post-apocalyptic bunker"
    assert calls["count"] == 2


def test_generate_idea_raises_after_max_attempts_of_invalid_json():
    def fake_llm(prompt, **kwargs):
        return "not json"

    with pytest.raises(ideas.IdeaGenerationError):
        ideas.generate_idea(recent=[], call_llm=fake_llm, max_attempts=2)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ideas.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.ideas'`.

- [x] **Step 3: Implement `src/pipeline/ideas.py`**

```python
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
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ideas.py -v`
Expected: 4 passed.

- [x] **Step 5: Commit**

```bash
git add src/pipeline/ideas.py tests/test_ideas.py
git commit -m "feat: add 5-axis idea generator with dedup-aware prompting"
```

---

## Task 5: Storyboard Generator

**Files:**
- Create: `src/pipeline/storyboard.py`
- Test: `tests/test_storyboard.py`

**Interfaces:**
- Consumes: `pipeline.llm.call_llm` (same signature as Task 3); the 5-axis dict produced by Task 4's `generate_idea`.
- Produces:
  - `generate_storyboard(idea: dict, call_llm=llm.call_llm, max_attempts: int = 3) -> dict` returning `{"beats": [...], "title": str, "description": str, "tags": [str, ...]}`.
  - `validate_storyboard(storyboard: dict) -> None` (raises `StoryboardValidationError`).
  - Each beat dict has keys: `stage` (one of `setup`/`progress`/`twist`/`reveal`), `type` (`transform_video`/`still_pan`), `duration_sec` (number), `caption` (str), plus `prompt_start`+`prompt_end` (if `transform_video`) or `prompt`+`pan` (if `still_pan`, `pan` one of `in`/`out`/`left`/`right`).

  Task 9 (assembly) and the orchestrator (Task 12) consume this exact beat schema.

- [x] **Step 1: Write the failing tests**

`tests/test_storyboard.py`:
```python
import json
import pytest
from pipeline import storyboard


IDEA = {
    "location": "inside a school bus",
    "concept": "post-apocalyptic bunker",
    "hook": "hidden room behind the driver's seat",
    "visual_style": "photorealistic",
    "audio_mood": "tense and driving",
}

VALID_STORYBOARD = {
    "beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "empty rusty school bus exterior",
         "pan": "in", "duration_sec": 4, "caption": "found this abandoned school bus..."},
        {"stage": "progress", "type": "transform_video", "prompt_start": "gutted school bus interior",
         "prompt_end": "half-built bunker interior with metal walls", "duration_sec": 5,
         "caption": "day 1: stripping it down"},
        {"stage": "twist", "type": "transform_video", "prompt_start": "half-built bunker interior",
         "prompt_end": "bunker interior revealing a hidden steel door", "duration_sec": 5,
         "caption": "wait... there's a hidden room?"},
        {"stage": "reveal", "type": "still_pan", "prompt": "finished bunker school bus interior, dramatic lighting",
         "pan": "out", "duration_sec": 4, "caption": "the finished bunker bus"},
        {"stage": "reveal", "type": "transform_video", "prompt_start": "bunker bus interior daytime",
         "prompt_end": "bunker bus interior with lights on at night", "duration_sec": 5,
         "caption": "home sweet bunker"},
        {"stage": "progress", "type": "transform_video", "prompt_start": "bare metal walls",
         "prompt_end": "insulated and painted walls", "duration_sec": 5,
         "caption": "insulating everything"},
        {"stage": "setup", "type": "still_pan", "prompt": "tools laid out before starting",
         "pan": "left", "duration_sec": 4, "caption": "let's get started"},
    ],
    "title": "I Turned an Abandoned School Bus Into a Secret Bunker",
    "description": "Watch this school bus get transformed into a hidden bunker, room by room.",
    "tags": ["ai build", "bunker", "school bus", "shorts"],
}


def test_generate_storyboard_returns_parsed_dict():
    def fake_llm(prompt, **kwargs):
        return json.dumps(VALID_STORYBOARD)

    result = storyboard.generate_storyboard(IDEA, call_llm=fake_llm)
    assert result["title"] == VALID_STORYBOARD["title"]
    assert len(result["beats"]) == 7


def test_generate_storyboard_includes_idea_axes_in_prompt():
    captured = {}

    def fake_llm(prompt, **kwargs):
        captured["prompt"] = prompt
        return json.dumps(VALID_STORYBOARD)

    storyboard.generate_storyboard(IDEA, call_llm=fake_llm)
    assert "school bus" in captured["prompt"]
    assert "hidden room behind the driver's seat" in captured["prompt"]


def test_generate_storyboard_retries_when_validation_fails_then_succeeds():
    too_short = dict(VALID_STORYBOARD)
    too_short["beats"] = VALID_STORYBOARD["beats"][:1]  # only 4 sec, fails min duration + stage coverage
    calls = {"count": 0}

    def fake_llm(prompt, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return json.dumps(too_short)
        return json.dumps(VALID_STORYBOARD)

    result = storyboard.generate_storyboard(IDEA, call_llm=fake_llm)
    assert len(result["beats"]) == 7
    assert calls["count"] == 2


def test_validate_storyboard_rejects_under_30_seconds():
    bad = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
         "duration_sec": 5, "caption": "x"},
    ], "title": "t", "description": "d", "tags": []}
    with pytest.raises(storyboard.StoryboardValidationError, match="30"):
        storyboard.validate_storyboard(bad)


def test_validate_storyboard_rejects_missing_stage():
    beats = [dict(b) for b in VALID_STORYBOARD["beats"]]
    for b in beats:
        if b["stage"] == "twist":
            b["stage"] = "progress"  # remove the only "twist" beat
    bad = {**VALID_STORYBOARD, "beats": beats}
    with pytest.raises(storyboard.StoryboardValidationError, match="twist"):
        storyboard.validate_storyboard(bad)


def test_validate_storyboard_accepts_valid_storyboard():
    storyboard.validate_storyboard(VALID_STORYBOARD)  # should not raise
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_storyboard.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.storyboard'`.

- [x] **Step 3: Implement `src/pipeline/storyboard.py`**

```python
import json
from pipeline import llm as llm_module

_REQUIRED_STAGES = {"setup", "progress", "twist", "reveal"}
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
    total_duration = sum(b.get("duration_sec", 0) for b in beats)
    if total_duration < _MIN_DURATION_SEC:
        raise StoryboardValidationError(
            f"total duration {total_duration}s is under the required {_MIN_DURATION_SEC}s minimum"
        )
    stages_present = {b.get("stage") for b in beats}
    missing = _REQUIRED_STAGES - stages_present
    if missing:
        raise StoryboardValidationError(f"storyboard is missing required stage(s): {sorted(missing)}")
    for i, b in enumerate(beats):
        if b.get("type") == "transform_video":
            if not b.get("prompt_start") or not b.get("prompt_end"):
                raise StoryboardValidationError(f"beat {i} is transform_video but missing prompt_start/prompt_end")
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
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_storyboard.py -v`
Expected: 6 passed.

- [x] **Step 5: Commit**

```bash
git add src/pipeline/storyboard.py tests/test_storyboard.py
git commit -m "feat: add storyboard generator with 30s/4-stage validation"
```

---

## Task 6: Music Picker

**Files:**
- Create: `src/pipeline/music.py`
- Create: `assets/music/manifest.json`
- Create: `assets/music/README.md`
- Test: `tests/test_music.py`

**Interfaces:**
- Consumes: nothing external — reads `assets/music/manifest.json`.
- Produces: `pick_music(mood: str, manifest_path: str = "assets/music/manifest.json", used_recently: list[str] | None = None) -> str` returning a file path (string) relative to `assets/music/`. Task 9 (assembly) and the orchestrator consume this path.

**Manual prerequisite (not automatable):** YouTube's Audio Library has no public API — tracks must be downloaded once by hand from https://studio.youtube.com → Audio Library, using only tracks marked safe for monetized use with no attribution burden (or "attribution required" tracks paired with the attribution text stored in the manifest). This task creates the manifest format and a `README.md` documenting the manual step; it does not (and cannot) download real audio files as part of automated implementation.

- [x] **Step 1: Write the failing tests**

`tests/test_music.py`:
```python
import json
import pytest
from pipeline import music


MANIFEST = {
    "tense and driving": [{"file": "tense_1.mp3", "attribution": ""}],
    "upbeat": [
        {"file": "upbeat_1.mp3", "attribution": ""},
        {"file": "upbeat_2.mp3", "attribution": ""},
    ],
}


def _write_manifest(tmp_path, data=MANIFEST):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_pick_music_returns_a_track_matching_mood(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    result = music.pick_music("tense and driving", manifest_path=manifest_path)
    assert result == "tense_1.mp3"


def test_pick_music_falls_back_to_any_track_when_mood_not_found(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    result = music.pick_music("completely unknown mood", manifest_path=manifest_path)
    assert result in {"tense_1.mp3", "upbeat_1.mp3", "upbeat_2.mp3"}


def test_pick_music_avoids_recently_used_when_alternative_exists(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    result = music.pick_music("upbeat", manifest_path=manifest_path, used_recently=["upbeat_1.mp3"])
    assert result == "upbeat_2.mp3"


def test_pick_music_raises_when_manifest_is_empty(tmp_path):
    manifest_path = _write_manifest(tmp_path, data={})
    with pytest.raises(music.NoMusicAvailableError):
        music.pick_music("anything", manifest_path=manifest_path)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_music.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.music'`.

- [x] **Step 3: Implement `src/pipeline/music.py`**

```python
import json
import random


class NoMusicAvailableError(Exception):
    pass


def _all_tracks(manifest: dict) -> list[str]:
    return [entry["file"] for tracks in manifest.values() for entry in tracks]


def pick_music(mood: str, manifest_path: str = "assets/music/manifest.json",
                used_recently: list[str] | None = None) -> str:
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    used_recently = used_recently or []
    candidates = [entry["file"] for entry in manifest.get(mood, [])]
    if not candidates:
        candidates = _all_tracks(manifest)
    if not candidates:
        raise NoMusicAvailableError(f"no music tracks found in {manifest_path}")

    unused = [c for c in candidates if c not in used_recently]
    pool = unused if unused else candidates
    return random.choice(pool)
```

- [x] **Step 4: Create `assets/music/manifest.json`**

```json
{}
```

- [x] **Step 5: Create `assets/music/README.md`**

```markdown
# Music assets

YouTube's Audio Library has no public API, so tracks must be added here by hand:

1. Go to https://studio.youtube.com → Audio Library.
2. Filter to tracks that are safe for monetized use (no attribution required, or note the
   attribution text if required).
3. Download the mp3 and place it in this folder.
4. Add an entry to `manifest.json` under a mood key matching the `audio_mood` values the
   idea generator produces (freeform strings are fine — `pick_music` falls back to any
   track if no exact mood match exists), e.g.:

   ```json
   {
     "tense and driving": [{"file": "tense_1.mp3", "attribution": ""}],
     "upbeat": [{"file": "upbeat_1.mp3", "attribution": ""}]
   }
   ```

Add at least 8-10 tracks across a few moods before the first real pipeline run, so
`pick_music` has real variety instead of reusing the same track every day.
```

- [x] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_music.py -v`
Expected: 4 passed.

- [x] **Step 7: Commit**

```bash
git add src/pipeline/music.py tests/test_music.py assets/music/manifest.json assets/music/README.md
git commit -m "feat: add music picker and document manual audio-library setup step"
```

---

## Task 7: Image Generation Client (Nano Banana Pro)

**Files:**
- Create: `src/pipeline/image_gen.py`
- Test: `tests/test_image_gen.py`

**Interfaces:**
- Consumes: `GEMINI_API_KEY` env var.
- Produces: `generate_image(prompt: str, out_path: str) -> str` (returns `out_path`, writes a PNG file there). Task 9 (assembly) and the orchestrator call this for every beat's keyframe(s).

**Before implementing:** the Gemini image-generation response schema for `gemini-3-pro-image-preview` is new enough that it should be double-checked against the live docs at https://ai.google.dev/gemini-api/docs/image-generation before relying on this in production. The implementation below follows Gemini's documented `generateContent` + `responseModalities: ["IMAGE"]` pattern; adjust the response-parsing path in Step 3 if the live schema differs.

- [x] **Step 1: Write the failing tests**

`tests/test_image_gen.py`:
```python
import base64
from unittest.mock import patch, MagicMock
from pipeline import image_gen


TINY_PNG_BASE64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake-png-bytes").decode()


def _fake_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"inlineData": {"mimeType": "image/png", "data": TINY_PNG_BASE64}}]
            }
        }]
    }
    return resp


@patch("pipeline.image_gen.requests.post")
def test_generate_image_writes_decoded_png_to_out_path(mock_post, tmp_path):
    mock_post.return_value = _fake_response()
    out_path = str(tmp_path / "keyframe.png")

    result = image_gen.generate_image("a rusty school bus exterior", out_path)

    assert result == out_path
    with open(out_path, "rb") as f:
        assert f.read() == base64.b64decode(TINY_PNG_BASE64)


@patch("pipeline.image_gen.requests.post")
def test_generate_image_sends_prompt_in_request_body(mock_post, tmp_path):
    mock_post.return_value = _fake_response()
    image_gen.generate_image("a rusty school bus exterior", str(tmp_path / "out.png"))

    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["contents"][0]["parts"][0]["text"] == "a rusty school bus exterior"


@patch("pipeline.image_gen.requests.post")
def test_generate_image_raises_on_non_200(mock_post, tmp_path):
    resp = MagicMock()
    resp.status_code = 400
    resp.text = "bad request"
    mock_post.return_value = resp

    import pytest
    with pytest.raises(image_gen.ImageGenerationError):
        image_gen.generate_image("prompt", str(tmp_path / "out.png"))
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_image_gen.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.image_gen'`.

- [x] **Step 3: Implement `src/pipeline/image_gen.py`**

```python
import base64
import os
import requests

_MODEL = "gemini-3-pro-image-preview"
_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"


class ImageGenerationError(Exception):
    pass


def generate_image(prompt: str, out_path: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    response = requests.post(
        _ENDPOINT,
        params={"key": api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        },
        timeout=120,
    )
    if response.status_code != 200:
        raise ImageGenerationError(f"image generation failed ({response.status_code}): {response.text}")

    data = response.json()
    try:
        b64_data = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError) as exc:
        raise ImageGenerationError(f"unexpected response shape: {data}") from exc

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return out_path
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_image_gen.py -v`
Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add src/pipeline/image_gen.py tests/test_image_gen.py
git commit -m "feat: add Nano Banana Pro image generation client"
```

---

## Task 8: Video Generation Client (Hailuo First-Last-Frame)

**Files:**
- Create: `src/pipeline/video_gen.py`
- Test: `tests/test_video_gen.py`

**Interfaces:**
- Consumes: `MINIMAX_API_KEY` env var; two image file paths (produced by Task 7's `generate_image`).
- Produces: `generate_video_segment(start_image_path: str, end_image_path: str, duration_sec: int, out_path: str) -> str` (returns `out_path`, writes an mp4 file there). The orchestrator calls this for every `transform_video` beat.

**Before implementing:** verify the current MiniMax/Hailuo video generation API shape (submit/poll/retrieve endpoints and field names) against https://www.minimax.io/platform/document before relying on this in production — the implementation below follows their documented async submit → poll → retrieve-download-url pattern; adjust endpoint paths/field names in Step 3 if they've changed.

- [x] **Step 1: Write the failing tests**

`tests/test_video_gen.py`:
```python
import base64
from unittest.mock import patch, MagicMock
import pytest
from pipeline import video_gen


def _resp(json_body, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    r.content = b"fake-mp4-bytes"
    return r


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_submits_polls_and_downloads(mock_post, mock_get, tmp_path):
    start = tmp_path / "start.png"
    end = tmp_path / "end.png"
    start.write_bytes(b"start-bytes")
    end.write_bytes(b"end-bytes")
    out_path = str(tmp_path / "clip.mp4")

    mock_post.return_value = _resp({"task_id": "task-123"})
    mock_get.side_effect = [
        _resp({"status": "Processing"}),
        _resp({"status": "Success", "file_id": "file-456"}),
        _resp({"file": {"download_url": "https://example.com/clip.mp4"}}),
        _resp({}),  # the final requests.get is the actual file download
    ]
    mock_get.side_effect[-1].content = b"fake-mp4-bytes"

    result = video_gen.generate_video_segment(str(start), str(end), 5, out_path, poll_interval_sec=0)

    assert result == out_path
    with open(out_path, "rb") as f:
        assert f.read() == b"fake-mp4-bytes"


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_raises_on_task_failure(mock_post, mock_get, tmp_path):
    start = tmp_path / "start.png"
    end = tmp_path / "end.png"
    start.write_bytes(b"s")
    end.write_bytes(b"e")

    mock_post.return_value = _resp({"task_id": "task-123"})
    mock_get.side_effect = [_resp({"status": "Fail"})]

    with pytest.raises(video_gen.VideoGenerationError):
        video_gen.generate_video_segment(str(start), str(end), 5, str(tmp_path / "clip.mp4"),
                                          poll_interval_sec=0)


@patch("pipeline.video_gen.requests.get")
@patch("pipeline.video_gen.requests.post")
def test_generate_video_segment_raises_after_max_polls(mock_post, mock_get, tmp_path):
    start = tmp_path / "start.png"
    end = tmp_path / "end.png"
    start.write_bytes(b"s")
    end.write_bytes(b"e")

    mock_post.return_value = _resp({"task_id": "task-123"})
    mock_get.return_value = _resp({"status": "Processing"})

    with pytest.raises(video_gen.VideoGenerationError, match="timed out"):
        video_gen.generate_video_segment(str(start), str(end), 5, str(tmp_path / "clip.mp4"),
                                          poll_interval_sec=0, max_polls=3)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_video_gen.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.video_gen'`.

- [x] **Step 3: Implement `src/pipeline/video_gen.py`**

```python
import base64
import os
import time
import requests

_BASE_URL = "https://api.minimax.chat/v1"
_MODEL = "MiniMax-Hailuo-2.3"


class VideoGenerationError(Exception):
    pass


def _headers():
    return {"Authorization": f"Bearer {os.environ.get('MINIMAX_API_KEY', '')}"}


def _image_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def generate_video_segment(start_image_path: str, end_image_path: str, duration_sec: int,
                            out_path: str, poll_interval_sec: int = 5, max_polls: int = 60) -> str:
    submit_resp = requests.post(
        f"{_BASE_URL}/video_generation",
        headers=_headers(),
        json={
            "model": _MODEL,
            "first_frame_image": _image_to_b64(start_image_path),
            "last_frame_image": _image_to_b64(end_image_path),
            "duration": duration_sec,
        },
        timeout=60,
    )
    if submit_resp.status_code != 200:
        raise VideoGenerationError(f"submit failed ({submit_resp.status_code}): {submit_resp.text}")
    task_id = submit_resp.json()["task_id"]

    file_id = None
    for _ in range(max_polls):
        status_resp = requests.get(f"{_BASE_URL}/query/video_generation",
                                    headers=_headers(), params={"task_id": task_id}, timeout=30)
        status_body = status_resp.json()
        status = status_body.get("status")
        if status == "Success":
            file_id = status_body["file_id"]
            break
        if status == "Fail":
            raise VideoGenerationError(f"video generation task {task_id} failed: {status_body}")
        if poll_interval_sec:
            time.sleep(poll_interval_sec)
    if file_id is None:
        raise VideoGenerationError(f"video generation task {task_id} timed out after {max_polls} polls")

    retrieve_resp = requests.get(f"{_BASE_URL}/files/retrieve",
                                  headers=_headers(), params={"file_id": file_id}, timeout=30)
    download_url = retrieve_resp.json()["file"]["download_url"]

    file_resp = requests.get(download_url, timeout=120)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(file_resp.content)
    return out_path
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_video_gen.py -v`
Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add src/pipeline/video_gen.py tests/test_video_gen.py
git commit -m "feat: add Hailuo first-last-frame video generation client"
```

---

## Task 9: Video Assembly (ffmpeg)

**Files:**
- Create: `src/pipeline/assemble.py`
- Test: `tests/test_assemble.py`

**Interfaces:**
- Consumes: a `storyboard` dict (Task 5 shape), a parallel `asset_paths: list[str]` (one path per beat, `.png` from Task 7 for `still_pan` beats or `.mp4` from Task 8 for `transform_video` beats), a `music_path` (from Task 6), and a `work_dir` for intermediates.
- Produces: `assemble_video(storyboard: dict, asset_paths: list[str], music_path: str, out_path: str, work_dir: str = "work") -> str` (returns `out_path`, a finished 1080×1920 mp4 with captions burned in and music mixed under).

- [x] **Step 1: Write the failing tests**

These tests build real tiny fixture assets with ffmpeg/Pillow (no mocking — `assemble.py` never makes network calls, so its tests exercise the real ffmpeg binary against fast, tiny inputs) and check the output with `ffprobe`.

`tests/test_assemble.py`:
```python
import json
import subprocess
import wave
import struct
from PIL import Image
from pipeline import assemble


def _make_still(path, color=(200, 50, 50)):
    Image.new("RGB", (640, 480), color).save(path)


def _make_clip(path, duration_sec=2, color="red"):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=640x480:d={duration_sec}",
        "-pix_fmt", "yuv420p", path,
    ], check=True, capture_output=True)


def _make_silent_wav(path, duration_sec=10):
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * duration_sec)


def _probe_duration(path) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", path,
    ], check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def _probe_resolution(path) -> tuple[int, int]:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", path,
    ], check=True, capture_output=True, text=True)
    stream = json.loads(result.stdout)["streams"][0]
    return stream["width"], stream["height"]


def test_assemble_video_produces_output_with_expected_total_duration(tmp_path):
    still1 = str(tmp_path / "still1.png")
    clip1 = str(tmp_path / "clip1.mp4")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_clip(clip1, duration_sec=3)
    _make_silent_wav(music, duration_sec=10)

    storyboard = {
        "beats": [
            {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
             "duration_sec": 4, "caption": "intro caption"},
            {"stage": "progress", "type": "transform_video", "prompt_start": "a", "prompt_end": "b",
             "duration_sec": 3, "caption": "progress caption"},
        ],
    }

    result = assemble.assemble_video(storyboard, [still1, clip1], music, out_path, work_dir=str(tmp_path / "work"))

    assert result == out_path
    duration = _probe_duration(out_path)
    assert 6.5 <= duration <= 7.5  # 4s + 3s, small ffmpeg rounding tolerance


def test_assemble_video_output_is_vertical_1080x1920(tmp_path):
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_silent_wav(music, duration_sec=5)

    storyboard = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
         "duration_sec": 4, "caption": "intro caption"},
    ]}

    assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))
    assert _probe_resolution(out_path) == (1080, 1920)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_assemble.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.assemble'`.

- [x] **Step 3: Implement `src/pipeline/assemble.py`**

```python
import os
import subprocess

_WIDTH = 1080
_HEIGHT = 1920
_FPS = 30

_PAN_FILTERS = {
    "in": "zoompan=z='min(zoom+0.0015,1.3)':d={frames}:s={w}x{h}:fps={fps}",
    "out": "zoompan=z='if(eq(on,1),1.3,max(1.3-0.0015*on,1.0))':d={frames}:s={w}x{h}:fps={fps}",
    "left": "zoompan=z=1.15:x='if(eq(on,1),iw*0.15,x-1)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    "right": "zoompan=z=1.15:x='if(eq(on,1),0,x+1)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
}


def _escape_caption(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _drawtext_filter(caption: str) -> str:
    escaped = _escape_caption(caption)
    return (
        f"drawtext=text='{escaped}':fontcolor=white:fontsize=64:"
        "borderw=4:bordercolor=black:x=(w-text_w)/2:y=h-th-160"
    )


def _build_still_clip(image_path: str, duration_sec: float, pan: str, caption: str, out_path: str) -> None:
    frames = int(duration_sec * _FPS)
    pan_filter = _PAN_FILTERS[pan].format(frames=frames, w=_WIDTH, h=_HEIGHT, fps=_FPS)
    vf = f"scale={_WIDTH}:{_HEIGHT}:force_original_aspect_ratio=increase,crop={_WIDTH}:{_HEIGHT},{pan_filter},{_drawtext_filter(caption)}"
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", str(duration_sec),
        "-vf", vf, "-pix_fmt", "yuv420p", "-r", str(_FPS), out_path,
    ], check=True, capture_output=True)


def _build_video_clip(video_path: str, duration_sec: float, caption: str, out_path: str) -> None:
    vf = f"scale={_WIDTH}:{_HEIGHT}:force_original_aspect_ratio=increase,crop={_WIDTH}:{_HEIGHT},{_drawtext_filter(caption)}"
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path, "-t", str(duration_sec),
        "-vf", vf, "-pix_fmt", "yuv420p", "-r", str(_FPS), "-an", out_path,
    ], check=True, capture_output=True)


def _concat_clips(clip_paths: list[str], work_dir: str, out_path: str) -> None:
    list_path = os.path.join(work_dir, "concat_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for path in clip_paths:
            f.write(f"file '{os.path.abspath(path)}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path,
    ], check=True, capture_output=True)


def _mix_music(video_path: str, music_path: str, out_path: str) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path, "-i", music_path,
        "-filter_complex", "[1:a]volume=0.5[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", out_path,
    ], check=True, capture_output=True)


def assemble_video(storyboard: dict, asset_paths: list[str], music_path: str,
                    out_path: str, work_dir: str = "work") -> str:
    os.makedirs(work_dir, exist_ok=True)
    beats = storyboard["beats"]
    clip_paths = []
    for i, (beat, asset_path) in enumerate(zip(beats, asset_paths)):
        clip_path = os.path.join(work_dir, f"beat_{i}.mp4")
        if beat["type"] == "still_pan":
            _build_still_clip(asset_path, beat["duration_sec"], beat["pan"], beat["caption"], clip_path)
        else:
            _build_video_clip(asset_path, beat["duration_sec"], beat["caption"], clip_path)
        clip_paths.append(clip_path)

    concatenated_path = os.path.join(work_dir, "concatenated.mp4")
    _concat_clips(clip_paths, work_dir, concatenated_path)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    _mix_music(concatenated_path, music_path, out_path)
    return out_path
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_assemble.py -v`
Expected: 2 passed. (These tests shell out to real `ffmpeg`/`ffprobe` and take a few seconds — that's expected.)

- [x] **Step 5: Commit**

```bash
git add src/pipeline/assemble.py tests/test_assemble.py
git commit -m "feat: add ffmpeg assembly (Ken Burns stills, captions, music mix)"
```

---

## Task 10: Telegram Approval Gate

**Files:**
- Create: `src/pipeline/telegram_approval.py`
- Test: `tests/test_telegram_approval.py`

**Interfaces:**
- Consumes: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` env vars; a finished video path (from Task 9's `assemble_video`).
- Produces: `request_approval(video_path: str, title: str, description: str, poll_interval_sec: int = 15, timeout_sec: int = 3600) -> bool`. The orchestrator (Task 12) uses this return value to decide whether to publish.

- [x] **Step 1: Write the failing tests**

`tests/test_telegram_approval.py`:
```python
from unittest.mock import patch, MagicMock
from pipeline import telegram_approval


def _resp(json_body):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = json_body
    return r


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_returns_true_on_approve_callback(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.return_value = _resp({"result": [
        {"update_id": 1, "callback_query": {"data": "approve",
         "message": {"message_id": 42}, "id": "cbq-1"}}
    ]})

    result = telegram_approval.request_approval(str(video_path), "title", "desc", poll_interval_sec=0)
    assert result is True


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_returns_false_on_reject_callback(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.return_value = _resp({"result": [
        {"update_id": 1, "callback_query": {"data": "reject",
         "message": {"message_id": 42}, "id": "cbq-1"}}
    ]})

    result = telegram_approval.request_approval(str(video_path), "title", "desc", poll_interval_sec=0)
    assert result is False


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_ignores_callbacks_for_other_messages(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.side_effect = [
        _resp({"result": [
            {"update_id": 1, "callback_query": {"data": "approve",
             "message": {"message_id": 999}, "id": "cbq-1"}}
        ]}),
        _resp({"result": [
            {"update_id": 2, "callback_query": {"data": "approve",
             "message": {"message_id": 42}, "id": "cbq-2"}}
        ]}),
    ]

    result = telegram_approval.request_approval(str(video_path), "title", "desc", poll_interval_sec=0)
    assert result is True
    assert mock_get.call_count == 2


@patch("pipeline.telegram_approval.requests.get")
@patch("pipeline.telegram_approval.requests.post")
def test_request_approval_times_out_to_false(mock_post, mock_get, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video")

    mock_post.return_value = _resp({"result": {"message_id": 42}})
    mock_get.return_value = _resp({"result": []})

    result = telegram_approval.request_approval(str(video_path), "title", "desc",
                                                  poll_interval_sec=0, timeout_sec=0)
    assert result is False
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_telegram_approval.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.telegram_approval'`.

- [x] **Step 3: Implement `src/pipeline/telegram_approval.py`**

```python
import json
import os
import time
import requests

_API_BASE = "https://api.telegram.org"


def _bot_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _chat_id() -> str:
    return os.environ.get("TELEGRAM_CHAT_ID", "")


def _send_video(video_path: str, caption: str) -> int:
    with open(video_path, "rb") as f:
        response = requests.post(
            f"{_API_BASE}/bot{_bot_token()}/sendVideo",
            data={
                "chat_id": _chat_id(),
                "caption": caption,
                "reply_markup": json.dumps({
                    "inline_keyboard": [[
                        {"text": "Approve \u2705", "callback_data": "approve"},
                        {"text": "Reject \u274c", "callback_data": "reject"},
                    ]]
                }),
            },
            files={"video": f},
            timeout=120,
        )
    return response.json()["result"]["message_id"]


def _poll_for_decision(message_id: int, poll_interval_sec: int, timeout_sec: int) -> str | None:
    elapsed = 0
    offset = None
    while elapsed <= timeout_sec:
        params = {"timeout": 0}
        if offset is not None:
            params["offset"] = offset
        response = requests.get(f"{_API_BASE}/bot{_bot_token()}/getUpdates", params=params, timeout=30)
        for update in response.json().get("result", []):
            offset = update["update_id"] + 1
            callback = update.get("callback_query")
            if callback and callback["message"]["message_id"] == message_id:
                return callback["data"]
        if elapsed >= timeout_sec:
            break
        if poll_interval_sec:
            time.sleep(poll_interval_sec)
        elapsed += poll_interval_sec if poll_interval_sec else timeout_sec + 1
    return None


def request_approval(video_path: str, title: str, description: str,
                      poll_interval_sec: int = 15, timeout_sec: int = 3600) -> bool:
    caption = f"{title}\n\n{description}"
    message_id = _send_video(video_path, caption)
    decision = _poll_for_decision(message_id, poll_interval_sec, timeout_sec)
    return decision == "approve"
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_telegram_approval.py -v`
Expected: 4 passed.

- [x] **Step 5: Commit**

```bash
git add src/pipeline/telegram_approval.py tests/test_telegram_approval.py
git commit -m "feat: add Telegram human-approval gate"
```

---

## Task 11: YouTube Publish

**Files:**
- Create: `src/pipeline/youtube_publish.py`
- Test: `tests/test_youtube_publish.py`

**Interfaces:**
- Consumes: `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` env vars; a finished video path (Task 9); title/description/tags (Task 5's storyboard output).
- Produces: `publish_video(video_path: str, title: str, description: str, tags: list[str], contains_synthetic_media: bool = True) -> str` returning the published YouTube video ID. The orchestrator uses this ID with `state.record_published`.

**One-time manual prerequisite (not automatable in code):** a Google Cloud OAuth client (Client ID/Secret) with the YouTube Data API v3 enabled, and a refresh token obtained once via the OAuth consent flow for the channel's Google account (e.g. using `google-auth-oauthlib`'s local-server flow interactively on a dev machine). Store the resulting `client_id`, `client_secret`, and `refresh_token` as GitHub Actions Secrets (wired up in Task 13). This task implements the automated *use* of that refresh token, not the one-time interactive consent step itself.

**Before implementing:** confirm the exact synthetic-media disclosure field name (used below as `status.containsSyntheticMedia`) against the current YouTube Data API v3 reference at https://developers.google.com/youtube/v3/docs/videos/insert before relying on this in production, since it was added recently.

- [x] **Step 1: Write the failing tests**

`tests/test_youtube_publish.py`:
```python
from unittest.mock import patch, MagicMock
import pytest
from pipeline import youtube_publish


def _resp(json_body, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body
    return r


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_returns_youtube_video_id(mock_post, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video-bytes")

    mock_post.side_effect = [
        _resp({"access_token": "token-abc"}),  # token refresh
        _resp({"id": "yt-video-123"}),          # upload
    ]

    result = youtube_publish.publish_video(str(video_path), "title", "desc", ["tag1", "tag2"])
    assert result == "yt-video-123"


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_sets_synthetic_media_disclosure(mock_post, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video-bytes")

    mock_post.side_effect = [
        _resp({"access_token": "token-abc"}),
        _resp({"id": "yt-video-123"}),
    ]

    youtube_publish.publish_video(str(video_path), "title", "desc", ["tag1"], contains_synthetic_media=True)

    upload_call = mock_post.call_args_list[1]
    metadata_json = upload_call.kwargs["files"]["metadata"][1]
    assert '"containsSyntheticMedia": true' in metadata_json or '"containsSyntheticMedia":true' in metadata_json


@patch("pipeline.youtube_publish.requests.post")
def test_publish_video_raises_on_upload_failure(mock_post, tmp_path):
    video_path = tmp_path / "final.mp4"
    video_path.write_bytes(b"fake-video-bytes")

    mock_post.side_effect = [
        _resp({"access_token": "token-abc"}),
        _resp({"error": "quota exceeded"}, status_code=403),
    ]

    with pytest.raises(youtube_publish.YouTubePublishError):
        youtube_publish.publish_video(str(video_path), "title", "desc", ["tag1"])
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_youtube_publish.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.youtube_publish'`.

- [x] **Step 3: Implement `src/pipeline/youtube_publish.py`**

```python
import json
import os
import requests

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubePublishError(Exception):
    pass


def _get_access_token() -> str:
    response = requests.post(_TOKEN_URL, data={
        "client_id": os.environ.get("YOUTUBE_CLIENT_ID", ""),
        "client_secret": os.environ.get("YOUTUBE_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("YOUTUBE_REFRESH_TOKEN", ""),
        "grant_type": "refresh_token",
    }, timeout=30)
    if response.status_code != 200:
        raise YouTubePublishError(f"token refresh failed ({response.status_code}): {response.text}")
    return response.json()["access_token"]


def publish_video(video_path: str, title: str, description: str, tags: list[str],
                   contains_synthetic_media: bool = True) -> str:
    access_token = _get_access_token()

    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": contains_synthetic_media,
        },
    }

    with open(video_path, "rb") as f:
        response = requests.post(
            _UPLOAD_URL,
            params={"uploadType": "multipart", "part": "snippet,status"},
            headers={"Authorization": f"Bearer {access_token}"},
            files={
                "metadata": (None, json.dumps(metadata), "application/json"),
                "video": (os.path.basename(video_path), f, "video/mp4"),
            },
            timeout=600,
        )

    if response.status_code not in (200, 201):
        raise YouTubePublishError(f"upload failed ({response.status_code}): {response.text}")
    return response.json()["id"]
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_youtube_publish.py -v`
Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add src/pipeline/youtube_publish.py tests/test_youtube_publish.py
git commit -m "feat: add YouTube publish client with synthetic-media disclosure"
```

---

## Task 12: Orchestrator

**Files:**
- Create: `src/pipeline/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: every module from Tasks 2–11, all called through their exact function names/signatures listed in those tasks' Interfaces sections.
- Produces: `run_pipeline(work_dir: str = "work", state_path: str = "state/history.json") -> dict | None` returning a result summary dict (`{"published": bool, "youtube_id": str | None, "cost_usd": float}`) or `None` if idea/storyboard generation failed outright. This is the function Task 13's GitHub Actions workflow invokes via a CLI entry point.

- [x] **Step 1: Write the failing tests**

Since every dependency is already unit-tested in isolation, the orchestrator test verifies *wiring*: that it calls each module in the right order with the right data flowing between them, using mocks for every dependency.

`tests/test_orchestrator.py`:
```python
from unittest.mock import patch, MagicMock
from pipeline import orchestrator


IDEA = {"location": "school bus", "concept": "bunker", "hook": "hidden room",
        "visual_style": "photoreal", "audio_mood": "tense"}
STORYBOARD = {
    "beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "p1", "pan": "in",
         "duration_sec": 15, "caption": "c1"},
        {"stage": "progress", "type": "transform_video", "prompt_start": "s1", "prompt_end": "e1",
         "duration_sec": 5, "caption": "c2"},
        {"stage": "twist", "type": "transform_video", "prompt_start": "s2", "prompt_end": "e2",
         "duration_sec": 5, "caption": "c3"},
        {"stage": "reveal", "type": "still_pan", "prompt": "p2", "pan": "out",
         "duration_sec": 8, "caption": "c4"},
    ],
    "title": "t", "description": "d", "tags": ["x"],
}


@patch("pipeline.orchestrator.youtube_publish.publish_video")
@patch("pipeline.orchestrator.telegram_approval.request_approval")
@patch("pipeline.orchestrator.assemble.assemble_video")
@patch("pipeline.orchestrator.music.pick_music")
@patch("pipeline.orchestrator.video_gen.generate_video_segment")
@patch("pipeline.orchestrator.image_gen.generate_image")
@patch("pipeline.orchestrator.storyboard.generate_storyboard")
@patch("pipeline.orchestrator.ideas.generate_idea")
def test_run_pipeline_publishes_on_approval(mock_idea, mock_storyboard, mock_image, mock_video,
                                             mock_music, mock_assemble, mock_approval, mock_publish,
                                             tmp_path):
    mock_idea.return_value = IDEA
    mock_storyboard.return_value = STORYBOARD
    mock_image.side_effect = lambda prompt, out_path: out_path
    mock_video.side_effect = lambda s, e, d, out_path, **kw: out_path
    mock_music.return_value = "track.mp3"
    mock_assemble.return_value = str(tmp_path / "final.mp4")
    mock_approval.return_value = True
    mock_publish.return_value = "yt-video-999"

    state_path = str(tmp_path / "history.json")
    result = orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=state_path)

    assert result == {"published": True, "youtube_id": "yt-video-999", "cost_usd": result["cost_usd"]}
    mock_publish.assert_called_once()
    import json
    saved = json.loads(open(state_path).read())
    assert len(saved["used_combos"]) == 1
    assert len(saved["published"]) == 1
    assert saved["published"][0]["youtube_id"] == "yt-video-999"


@patch("pipeline.orchestrator.youtube_publish.publish_video")
@patch("pipeline.orchestrator.telegram_approval.request_approval")
@patch("pipeline.orchestrator.assemble.assemble_video")
@patch("pipeline.orchestrator.music.pick_music")
@patch("pipeline.orchestrator.video_gen.generate_video_segment")
@patch("pipeline.orchestrator.image_gen.generate_image")
@patch("pipeline.orchestrator.storyboard.generate_storyboard")
@patch("pipeline.orchestrator.ideas.generate_idea")
def test_run_pipeline_does_not_publish_on_rejection(mock_idea, mock_storyboard, mock_image, mock_video,
                                                      mock_music, mock_assemble, mock_approval, mock_publish,
                                                      tmp_path):
    mock_idea.return_value = IDEA
    mock_storyboard.return_value = STORYBOARD
    mock_image.side_effect = lambda prompt, out_path: out_path
    mock_video.side_effect = lambda s, e, d, out_path, **kw: out_path
    mock_music.return_value = "track.mp3"
    mock_assemble.return_value = str(tmp_path / "final.mp4")
    mock_approval.return_value = False

    state_path = str(tmp_path / "history.json")
    result = orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=state_path)

    assert result["published"] is False
    assert result["youtube_id"] is None
    mock_publish.assert_not_called()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.orchestrator'`.

- [x] **Step 3: Implement `src/pipeline/orchestrator.py`**

```python
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
```

- [x] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: 2 passed.

- [x] **Step 5: Run the full test suite**

Run: `python -m pytest -v`
Expected: all tests across every module pass (state, llm, ideas, storyboard, music, image_gen, video_gen, assemble, telegram_approval, youtube_publish, orchestrator).

- [x] **Step 6: Commit**

```bash
git add src/pipeline/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator wiring the full daily pipeline"
```

---

## Task 13: GitHub Actions Daily Workflow

**Files:**
- Create: `.github/workflows/daily-shorts.yml`
- Modify: `README.md:1-6` (add setup/secrets instructions)

**Interfaces:**
- Consumes: `run_pipeline()` from Task 12 as the workflow's entry point; all the env vars listed in `.env.example` (Task 1), sourced from GitHub Actions Secrets.
- Produces: a scheduled CI job; no code interface (this is the deployment task).

- [x] **Step 1: Create the workflow file**

`.github/workflows/daily-shorts.yml`:
```yaml
name: Daily Shorts Pipeline

on:
  schedule:
    - cron: "0 14 * * *"  # 14:00 UTC daily; adjust to your preferred publish time
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    timeout-minutes: 90
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install ffmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Install Python dependencies
        run: python -m pip install -r requirements.txt

      - name: Run daily pipeline
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          MINIMAX_API_KEY: ${{ secrets.MINIMAX_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          YOUTUBE_CLIENT_ID: ${{ secrets.YOUTUBE_CLIENT_ID }}
          YOUTUBE_CLIENT_SECRET: ${{ secrets.YOUTUBE_CLIENT_SECRET }}
          YOUTUBE_REFRESH_TOKEN: ${{ secrets.YOUTUBE_REFRESH_TOKEN }}
        run: python -m pipeline.orchestrator

      - name: Commit updated state
        run: |
          git config user.name "shorts-pipeline-bot"
          git config user.email "actions@users.noreply.github.com"
          git add state/history.json
          git diff --cached --quiet || git commit -m "chore: update pipeline state [skip ci]"
          git push
```

- [x] **Step 2: Add setup instructions to `README.md`**

Read the current `README.md` first (created in the brainstorming phase), then append this section:

```markdown

## Setup

1. Populate `assets/music/` per `assets/music/README.md` (manual YouTube Audio Library download step).
2. Obtain a YouTube Data API OAuth refresh token once, interactively, for the target channel's
   Google account (Google Cloud Console → OAuth client → `google-auth-oauthlib` local-server flow).
3. Add these repository secrets under Settings → Secrets and variables → Actions:
   `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MINIMAX_API_KEY`, `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
4. Create a Telegram bot via [@BotFather](https://t.me/BotFather) for `TELEGRAM_BOT_TOKEN`, and
   get your numeric chat ID (e.g. by messaging the bot once and calling `getUpdates`) for
   `TELEGRAM_CHAT_ID`.
5. The workflow in `.github/workflows/daily-shorts.yml` runs daily at 14:00 UTC, or on-demand via
   the Actions tab ("Run workflow").
```

- [x] **Step 3: Verify the workflow YAML is valid**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-shorts.yml'))"`
Expected: no error (if `pyyaml` isn't installed, run `python -m pip install pyyaml` first just for this check — it is not a runtime dependency of the pipeline itself).

- [x] **Step 4: Commit**

```bash
git add .github/workflows/daily-shorts.yml README.md
git commit -m "ci: add daily GitHub Actions pipeline workflow"
```

- [x] **Step 5: Push everything to GitHub**

```bash
git push -u origin main
```

Expected: all commits from Tasks 1–13 appear on `https://github.com/MS-Won/Shorts`.

---

## Self-Review Notes

- **Spec coverage:** idea generation (Task 4), storyboard/30s+/4-stage validation (Task 5), music from local library standing in for YouTube Audio Library (Task 6), image+video asset generation at the cheap-tier cost model (Tasks 7–8, cost constants in Task 12), ffmpeg assembly with Ken Burns + captions + music (Task 9), Telegram approval gate (Task 10), YouTube publish with synthetic-media disclosure (Task 11), state persistence for dedup/cost/publish history (Task 2), GitHub Actions daily scheduling with secrets (Task 13) — every spec section (§3–§7) maps to a task.
- **Known external-API risk:** Tasks 7, 8, and 11 each carry an explicit pre-implementation verification note because Nano Banana Pro, Hailuo, and YouTube's synthetic-media field are recent/evolving APIs — this is a real risk to flag during execution, not a placeholder to fill in later.
- **Manual, non-automatable steps called out explicitly:** populating `assets/music/` (Task 6) and the one-time YouTube OAuth consent flow to obtain a refresh token (Task 11) — both documented as prerequisites rather than glossed over.
- **Out of scope, confirmed against spec §8:** trend/topic research engine, link-based topic cloner, multi-platform publishing, analytics/optimization loop, AI narrator character — none of these appear in this plan, matching the spec's explicit scope-out.
