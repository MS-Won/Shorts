# Validation Budget Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the daily pipeline from spending money once a validation-stage budget or review checkpoint is reached, so an unproven niche can't quietly burn cash before a human looks at the numbers.

**Architecture:** Two small additions to already-shipped code. `telegram_approval.py` gets a one-way `notify(text)` function (no buttons, no wait) alongside the existing two-way `request_approval()`. `orchestrator.py` gets a `_validation_guard(current_state)` pure function, called at the top of `run_pipeline` — before any paid call — that reads the existing `cost_log` in `state/history.json` and returns a block reason or `None`. Three new config values are threaded through as GitHub Actions **repository Variables** (not Secrets — they're not sensitive, and `VALIDATION_ACK_COUNT` specifically needs to be edited by a human on a regular cadence, which Variables support without a code change).

**Tech Stack:** Same as the rest of the pipeline — Python 3.11, `requests`, `pytest`, `unittest.mock`. No new dependencies.

## Global Constraints

- Validation-stage total spend ceiling: **$125** default (`VALIDATION_BUDGET_USD`).
- Checkpoint cadence: **every 10 videos** default (`VALIDATION_CHECKPOINT_EVERY`), tracked against `VALIDATION_ACK_COUNT` (default `0`), which a human raises by hand after reviewing YouTube Studio.
- Enforcement is mechanical (the system blocks); judgment stays human (deciding whether the numbers justify continuing is never automated — see design spec §8 for what's explicitly out of scope).
- `_validation_guard` must run **before** `ideas.generate_idea` — i.e. before the first paid call of any run — matching the existing `estimate_cost`/`MAX_COST_USD` pattern already in `orchestrator.py`.
- No `state/history.json` schema change: both checks derive from the existing `cost_log` list (`len()` for video count, `sum(cost_usd)` for spend).
- Commit messages in Korean, stating *why* (matches every existing commit on `main` and `CLAUDE.md`'s stated convention).
- GitHub Actions `vars.X` resolves to an **empty string**, not "unset," when a repository Variable doesn't exist yet — env-var parsing must treat `""` as "use the default," or a fresh checkout with no Variables configured will crash with `ValueError: could not convert string to float: ''`.

---

## File Structure

```
D:\shorts\
  src/pipeline/
    telegram_approval.py   # + notify(text) — one-way message, best-effort
    orchestrator.py         # + _env_float/_env_int helpers, 3 config constants,
                              #   _validation_guard(state), one new block in run_pipeline
  tests/
    test_telegram_approval.py   # + 3 tests for notify()
    test_orchestrator.py         # + notify added to the shared `mocks` fixture,
                                   #   5 direct _validation_guard tests, 1 run_pipeline
                                   #   integration test
  .github/workflows/daily-shorts.yml   # + 3 env lines sourced from vars.*
  README.md                             # + short "검증 단계 예산 관리" section
  docs/STATE.md                          # updated to reflect the new capability
  todo.md                                 # new completed entry + new "다음에 할 일" note
```

No new files. `telegram_approval.py` still owns "everything that talks to Telegram," `orchestrator.py` still owns "order, money, state" and no business logic beyond that — the guard is exactly that kind of decision, so it belongs there.

---

## Task 1: One-way Telegram notification

**Files:**
- Modify: `src/pipeline/telegram_approval.py` (append after `request_approval`, currently ending at line 113)
- Test: `tests/test_telegram_approval.py` (append; add `import requests` to the existing import block)

**Interfaces:**
- Consumes: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` env vars (same as the rest of the module); module-level `API_BASE` constant (already defined at line 14).
- Produces: `notify(text: str) -> None`. Task 2 calls this exactly as `telegram_approval.notify(reason)`.

- [ ] **Step 1: Write the failing tests**

Add `import requests` near the top of `tests/test_telegram_approval.py` (alongside the existing `from unittest.mock import patch, MagicMock` / `import pytest` / `from pipeline import telegram_approval` block), then append these three tests at the end of the file:

```python
@patch("pipeline.telegram_approval.requests.post")
def test_notify_sends_the_text_to_the_configured_chat(mock_post):
    telegram_approval.notify("검증 예산 소진")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "sendMessage" in args[0]
    assert kwargs["data"]["chat_id"] == "12345"
    assert kwargs["data"]["text"] == "검증 예산 소진"


@patch("pipeline.telegram_approval.requests.post")
def test_notify_does_nothing_when_credentials_are_missing(mock_post, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    telegram_approval.notify("should not send")
    mock_post.assert_not_called()


@patch("pipeline.telegram_approval.requests.post")
def test_notify_swallows_network_errors(mock_post):
    mock_post.side_effect = requests.RequestException("boom")
    telegram_approval.notify("network is down")  # must not raise
```

These rely on the file's existing `_credentials` autouse fixture (already sets `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` for every test unless a test deletes one, exactly as `test_request_approval_raises_when_credentials_are_missing` already does).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_telegram_approval.py -k notify -v`
Expected: 3 failures, each with `AttributeError: module 'pipeline.telegram_approval' has no attribute 'notify'`.

- [ ] **Step 3: Implement `notify`**

Append to `src/pipeline/telegram_approval.py`, after the existing `request_approval` function (after its closing `return decision == APPROVE` line):

```python


def notify(text: str) -> None:
    """A one-way heads-up — no buttons, no wait for a reply.

    Used when the pipeline stops itself (validation budget/checkpoint) or
    hits an unhandled failure, so a person finds out without going to check
    the Actions log. Best-effort: this fires from places where something has
    already gone wrong, so a failure here must never crash the caller and
    bury the real reason.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"{API_BASE}/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=30,
        )
    except requests.RequestException:
        pass
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_telegram_approval.py -v`
Expected: all tests pass (the 3 new ones plus every pre-existing test in the file — nothing else in this file changed).

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/telegram_approval.py tests/test_telegram_approval.py
git commit -m "$(cat <<'EOF'
feat: 텔레그램 단방향 알림 함수 notify() 추가

검증 예산/체크포인트 가드가 파이프라인을 스스로 멈출 때 사람에게 알릴 방법이
없었다. request_approval()은 버튼+대기가 필요해 이 용도엔 안 맞아서, 버튼 없이
메시지만 보내고 응답을 기다리지 않는 별도 함수로 분리했다.
EOF
)"
```

---

## Task 2: Validation budget/checkpoint guard in the orchestrator

**Files:**
- Modify: `src/pipeline/orchestrator.py:30-31` (insert new config after `MAX_STORYBOARD_ATTEMPTS`), `src/pipeline/orchestrator.py:79-91` (insert new function before `run_pipeline`, insert new block at the top of `run_pipeline`)
- Test: `tests/test_orchestrator.py` (modify the `mocks` fixture's `targets` dict; append new tests)

**Interfaces:**
- Consumes: `state.load_state`/the `current_state` dict shape (`{"used_combos": [...], "cost_log": [{"video_id", "cost_usd", "breakdown"}, ...], "published": [...]}` — unchanged, from Task 1's already-shipped `state.py`); Task 1's `telegram_approval.notify(text: str) -> None`.
- Produces: `_validation_guard(current_state: dict) -> str | None` (a private helper, but tested directly — matches the existing pattern of `orchestrator._make_video_id` being called directly from tests). `run_pipeline` gains a new early-exit path that returns `None`, same as its existing idea/storyboard-failure paths.

- [ ] **Step 1: Write the failing tests**

In `tests/test_orchestrator.py`, first modify the `mocks` fixture's `targets` dict (currently lines 41-49) to add a `notify` entry:

```python
    targets = {
        "idea": "pipeline.orchestrator.ideas.generate_idea",
        "storyboard": "pipeline.orchestrator.storyboard.generate_storyboard",
        "image": "pipeline.orchestrator.image_gen.generate_image",
        "video": "pipeline.orchestrator.video_gen.generate_video_segment",
        "music": "pipeline.orchestrator.music.pick_music",
        "assemble": "pipeline.orchestrator.assemble.assemble_video",
        "approval": "pipeline.orchestrator.telegram_approval.request_approval",
        "publish": "pipeline.orchestrator.youtube_publish.publish_video",
        "notify": "pipeline.orchestrator.telegram_approval.notify",
    }
```

(No change needed to the `with ExitStack() as stack:` block below it — it already builds `m` generically from whatever `targets` contains, and none of the existing tests need `notify` to return anything specific.)

Then append these tests at the end of the file:

```python
def _state_with_cost_log(entries):
    return {"used_combos": [], "cost_log": entries, "published": []}


def test_validation_guard_allows_when_under_budget_and_checkpoint(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 100.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 10)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)
    state_ = _state_with_cost_log([{"cost_usd": 4.0} for _ in range(5)])

    assert orchestrator._validation_guard(state_) is None


def test_validation_guard_blocks_when_budget_is_exhausted(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 20.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 100)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)
    state_ = _state_with_cost_log([{"cost_usd": 4.0} for _ in range(5)])  # $20.00 total

    reason = orchestrator._validation_guard(state_)
    assert reason is not None
    assert "예산" in reason


def test_validation_guard_blocks_at_the_checkpoint_boundary(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 1000.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 10)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)
    state_ = _state_with_cost_log([{"cost_usd": 1.0} for _ in range(10)])

    reason = orchestrator._validation_guard(state_)
    assert reason is not None
    assert "체크포인트" in reason


def test_validation_guard_allows_just_under_the_checkpoint_boundary(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 1000.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 10)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)
    state_ = _state_with_cost_log([{"cost_usd": 1.0} for _ in range(9)])

    assert orchestrator._validation_guard(state_) is None


def test_validation_guard_respects_a_raised_ack_count(monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 1000.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 10)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 10)  # last checkpoint was reviewed
    state_ = _state_with_cost_log([{"cost_usd": 1.0} for _ in range(10)])

    assert orchestrator._validation_guard(state_) is None


def test_run_pipeline_refuses_to_run_when_validation_guard_blocks(mocks, tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "VALIDATION_BUDGET_USD", 1.0)
    monkeypatch.setattr(orchestrator, "VALIDATION_CHECKPOINT_EVERY", 1000)
    monkeypatch.setattr(orchestrator, "VALIDATION_ACK_COUNT", 0)

    state_path = tmp_path / "history.json"
    state_path.write_text(json.dumps(_state_with_cost_log([{"cost_usd": 5.0}])))

    result = orchestrator.run_pipeline(work_dir=str(tmp_path / "work"), state_path=str(state_path))

    assert result is None
    mocks["idea"].assert_not_called()
    mocks["notify"].assert_called_once()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py -k validation_guard -v`
Expected: 6 failures. The 5 direct tests fail with `AttributeError: module 'pipeline.orchestrator' has no attribute '_validation_guard'` (or, for the `monkeypatch.setattr` calls themselves, `AttributeError: 'module' object has no attribute 'VALIDATION_BUDGET_USD'`, since neither the constants nor the function exist yet). The 6th (`test_run_pipeline_refuses_to_run_when_validation_guard_blocks`) fails the same way.

- [ ] **Step 3: Add the env-parsing helpers and config constants**

In `src/pipeline/orchestrator.py`, replace lines 30-31 (currently just `MAX_COST_USD = ...` and `MAX_STORYBOARD_ATTEMPTS = 3`) with:

```python
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
```

- [ ] **Step 4: Add `_validation_guard`**

In `src/pipeline/orchestrator.py`, insert this function right before `def run_pipeline(` (i.e. directly after `_affordable_storyboard`'s closing `return None`):

```python
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
```

- [ ] **Step 5: Wire the guard into `run_pipeline`**

In `src/pipeline/orchestrator.py`, `run_pipeline` currently starts:

```python
def run_pipeline(work_dir: str = "work", state_path: str = "state/history.json") -> dict | None:
    os.makedirs(work_dir, exist_ok=True)
    current_state = state.load_state(state_path)

    try:
        idea = ideas.generate_idea(recent=state.recent_combos(current_state))
```

Change it to:

```python
def run_pipeline(work_dir: str = "work", state_path: str = "state/history.json") -> dict | None:
    os.makedirs(work_dir, exist_ok=True)
    current_state = state.load_state(state_path)

    blocked = _validation_guard(current_state)
    if blocked is not None:
        telegram_approval.notify(blocked)
        print(f"pipeline aborted before spending anything: {blocked}")
        return None

    try:
        idea = ideas.generate_idea(recent=state.recent_combos(current_state))
```

(Only the four new lines are inserted; everything from `try:` onward is unchanged.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: all tests pass — the 6 new ones plus every pre-existing test in the file (the `mocks` fixture change is additive and doesn't affect tests that don't reference `mocks["notify"]`).

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest -v` (ffmpeg must be on `PATH` for `tests/test_assemble.py`, per the project's own `README.md` "로컬 개발" section — install via `winget install Gyan.FFmpeg` on Windows or `sudo apt-get install -y ffmpeg fonts-dejavu-core` on Linux if not already present; tests without it skip with a stated reason rather than failing).
Expected: all tests pass (or the ffmpeg-dependent ones skip cleanly), zero failures.

- [ ] **Step 8: Commit**

```bash
git add src/pipeline/orchestrator.py tests/test_orchestrator.py
git commit -m "$(cat <<'EOF'
feat: 검증 예산·체크포인트 가드 추가

니치가 수익화될지 검증 안 된 상태에서 영상당 $3~5씩 계속 나가는데, 조회수가
안 나오면 이 문턱(구독 1000명+조회수 1000만/90일)에 아예 못 미친 채 비용만
쌓일 수 있다. 누적 지출이 $125를 넘거나, 마지막 검토 이후 10편이 또 쌓이면
파이프라인이 스스로 멈추고 텔레그램으로 알린다. 판단(계속/중단)은 여전히
사람 몫이고, 시스템은 한도를 못 넘게 막는 역할만 한다.
EOF
)"
```

---

## Task 3: Wire the new config into the GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/daily-shorts.yml:55-56` (insert 3 lines after `MAX_COST_USD`)

**Interfaces:**
- Consumes: Task 2's `VALIDATION_BUDGET_USD`/`VALIDATION_CHECKPOINT_EVERY`/`VALIDATION_ACK_COUNT` env-var names (must match exactly — Task 2's `_env_float`/`_env_int` calls read these exact names).
- Produces: nothing further downstream — this is the deployment wiring, last link in the chain.

- [ ] **Step 1: Add the three env lines**

In `.github/workflows/daily-shorts.yml`, the "Run daily pipeline" step's `env:` block currently ends with:

```yaml
          APPROVAL_TIMEOUT_SEC: "1800"
          MAX_COST_USD: "5.0"
        run: python -m pipeline.orchestrator
```

Change it to:

```yaml
          APPROVAL_TIMEOUT_SEC: "1800"
          MAX_COST_USD: "5.0"
          # Repository Variables (Settings → Secrets and variables → Actions → Variables),
          # not Secrets — not sensitive, and VALIDATION_ACK_COUNT specifically needs
          # editing by hand after every checkpoint review. Unset resolves to "" here,
          # which orchestrator.py's _env_float/_env_int treat as "use the default"
          # (125 / 10 / 0) — see docs/superpowers/specs/2026-09-01-validation-budget-guard-design.md.
          VALIDATION_BUDGET_USD: ${{ vars.VALIDATION_BUDGET_USD }}
          VALIDATION_CHECKPOINT_EVERY: ${{ vars.VALIDATION_CHECKPOINT_EVERY }}
          VALIDATION_ACK_COUNT: ${{ vars.VALIDATION_ACK_COUNT }}
        run: python -m pipeline.orchestrator
```

- [ ] **Step 2: Verify the YAML is still valid**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-shorts.yml', encoding='utf-8'))"`
Expected: no output, no error (matches how the original workflow task was verified).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily-shorts.yml
git commit -m "$(cat <<'EOF'
ci: 검증 예산 설정값을 저장소 Variables로 워크플로에 연결

VALIDATION_ACK_COUNT는 체크포인트마다 사람이 직접 올려야 하는 값이라, 코드
수정 없이 GitHub 설정 화면에서 바로 바꿀 수 있는 Variables로 넣었다. 값을
아직 설정 안 해도 orchestrator.py 쪽 기본값(125/10/0)으로 정상 동작한다.
EOF
)"
```

---

## Task 4: Update the hand-off docs

**Files:**
- Modify: `README.md` (insert new section before `## 알려진 위험`)
- Modify: `docs/STATE.md`
- Modify: `todo.md`

**Interfaces:**
- Consumes: nothing (pure documentation).
- Produces: nothing consumed by other tasks — this is the last task, purely for the next person/session per `CLAUDE.md`'s stated convention ("세션을 시작하면 가장 먼저 `docs/STATE.md`를 읽어라").

- [ ] **Step 1: Add a README section documenting the new Variables**

In `README.md`, the "알려진 위험" section currently starts right after this paragraph (search for it — it's the paragraph ending "...state/history.json에 남고 다음 프롬프트에 주입된다."):

```markdown
5축 변형 시스템(장소·컨셉·훅·비주얼·오디오)은 단순한 다양성 장치가 아니라,
2026년 강화된 "inauthentic content" 정책에서 템플릿 대량생산으로 분류되지 않기
위한 장치다. 과거 조합은 `state/history.json`에 남고 다음 프롬프트에 주입된다.

## 알려진 위험
```

Insert a new section between them:

```markdown
5축 변형 시스템(장소·컨셉·훅·비주얼·오디오)은 단순한 다양성 장치가 아니라,
2026년 강화된 "inauthentic content" 정책에서 템플릿 대량생산으로 분류되지 않기
위한 장치다. 과거 조합은 `state/history.json`에 남고 다음 프롬프트에 주입된다.

## 검증 단계 예산 관리

수익화가 검증되지 않은 상태에서 영상당 $3~5씩 무한정 나가는 걸 막기 위해,
`orchestrator.py`가 매일 실행 전에 두 가지를 확인한다.

- 누적 지출이 `VALIDATION_BUDGET_USD`(기본 $125)를 넘으면 그날 실행을 거부한다.
- 마지막 검토 이후 `VALIDATION_CHECKPOINT_EVERY`(기본 10)편이 또 쌓이면 실행을
  거부한다. `VALIDATION_ACK_COUNT`(기본 0)를 검토한 영상 수로 올려야 재개된다.

두 경우 다 텔레그램으로 알림이 오고, 아무 비용도 쓰지 않은 채 멈춘다. 값은
저장소 Settings → Secrets and variables → Actions → **Variables** 탭에서
설정한다 (시크릿이 아니라 Variables인 이유: `VALIDATION_ACK_COUNT`는 체크포인트마다
사람이 직접 바꿔야 하는 값이라, 코드/워크플로 수정 없이 화면에서 바로 바꿀 수 있어야
한다). 아직 설정하지 않았다면 기본값(125 / 10 / 0)으로 동작한다.

## 알려진 위험
```

- [ ] **Step 2: Update `docs/STATE.md`**

Read the current `docs/STATE.md` first (it changes over time — always read before editing, don't assume the content described here is still exactly current). Update the following, keeping the file's existing tone and structure:

- The "검증 상태" line near the top: update the test count (98 → new total after Tasks 1–2 add tests) and the date, e.g. `**검증 상태**: \`python -m pytest\` N건 전부 통과 (2026-09-01 실행, ffmpeg 9.0.1)` — get the exact new count from Task 2 Step 7's actual `pytest -v` output rather than guessing.
- Add a line to the "코드" section's module table for the behavior change in `orchestrator.py` and `telegram_approval.py` (both already listed — just note the new responsibility in the existing "역할" column or add a one-line callout below the table, e.g. "`orchestrator.py`는 이제 검증 예산/체크포인트 가드도 확인한다").
- Add `VALIDATION_BUDGET_USD`, `VALIDATION_CHECKPOINT_EVERY`, `VALIDATION_ACK_COUNT` to the "외부 시스템" section's list of things not yet configured (they have working defaults, so this is informational, not a blocker like the missing API keys).

- [ ] **Step 3: Update `todo.md`**

Read the current `todo.md` first (same caveat as Step 2). Add a new completed entry under the "코드 (완료)" section, following the file's existing style (checked box, one-line summary, verification note):

```markdown
- [x] **검증 예산 가드 + 체크포인트 일시정지 추가**
  2026-09-01 완료. 누적 지출 $125 또는 검토 후 10편 초과 시 파이프라인이 스스로
  멈추고 텔레그램으로 알린다(`orchestrator._validation_guard` + `telegram_approval.notify`).
  `python -m pytest`로 신규 테스트 포함 전체 통과 확인. 스펙:
  `docs/superpowers/specs/2026-09-01-validation-budget-guard-design.md`.
```

- [ ] **Step 4: Commit**

```bash
git add README.md docs/STATE.md todo.md
git commit -m "$(cat <<'EOF'
docs: 검증 예산 가드 관련 인수인계 문서 갱신

README에 새 Variables 3종 설명 추가, STATE.md/todo.md를 이번 작업 반영해 갱신.
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** §3(설정값)→Task 3, §4(동작 로직)→Task 2, §5(알림)→Task 1, §6(상태 추적: "스키마 변경 불필요")→confirmed no `state.py` changes anywhere in this plan, §7(테스트 관점)→every bullet has a corresponding test in Task 1/2, §8(범위 밖)→nothing in this plan touches YouTube analytics APIs, Telegram-button-based checkpoint approval, or auto-disabling the guard.
- **Placeholder scan:** none found — every step has literal code, exact commands, and exact expected output; Task 4's doc-update steps give exact text to insert rather than "add appropriate notes," with the one necessarily-open item (exact new test count for STATE.md) explicitly pointed at where to get the real number rather than guessed.
- **Type consistency:** `_validation_guard(current_state: dict) -> str | None` used identically in Task 2's tests and its `run_pipeline` call site; `notify(text: str) -> None` used identically in Task 1's tests and Task 2's `telegram_approval.notify(blocked)` call; the `mocks` fixture's `notify` key matches the exact patch target `pipeline.orchestrator.telegram_approval.notify` used nowhere else under a different name.
