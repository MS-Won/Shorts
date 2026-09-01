# 지금 상태와 다음 할 일

> 이 파일은 **PC 사이를 넘어가는 유일한 인수인계 수단**이다.
> Claude의 로컬 메모리는 PC를 넘어오지 않는다. 설계 문서 6절이 "이 저장소가
> 공유 컨텍스트 역할을 한다"고 정한 것을 구체화한 파일이다.

**마지막 갱신**: 2026-09-01 · 작업 PC: 메인 데스크톱
<!-- 커밋 해시는 적지 않는다. 이 파일을 커밋하는 순간 값이 바뀌어 항상 어긋난다.
     시점이 필요하면 `git log -1 -- docs/STATE.md`로 확인할 것. -->
**검증 상태**: `python -m pytest` 126건 전부 통과 (2026-09-01 실행, ffmpeg 9.0.1)

---

## 한 줄 요약

**코드는 100% 끝났다. 남은 건 전부 사람 손이 필요한 계정·자산 준비다.**
음악 트랙(9개)과 텔레그램 봇(토큰·chat ID)은 이미 확보됨. 이번 세션에서 "실제로
쇼츠 1편을 테스트 제작"하는 절차를 `docs/testing-guide.md`로 정리했고,
`orchestrator.py`에 단계별(이미지/영상) 비용 콘솔 리포트를 추가했다. 아직
Gemini/MiniMax API 키가 없어 실제 생성은 다음 세션 몫이다.

---

## 지금 상태

### 저장소
- 브랜치 `main`, origin과 동기화됨. 작업 트리 깨끗함.
- 구현 계획서
  `docs/superpowers/plans/2026-08-31-ai-shorts-content-pipeline-implementation.md`의
  **13개 Task 체크박스 전부 완료.** 계획과 다르게 구현한 곳은 각 Task 아래
  인용 블록과 해당 커밋 메시지에 이유까지 적혀 있다.
- `origin/content-pipeline-implementation` 브랜치(+ 로컬 워크트리
  `.worktrees/content-pipeline`)가 **여전히 남아 있다.** 다른 세션이 독립적으로
  구현한 버전이었는데, main이 최종본으로 확정되면서 "텔레그램 chat_id 검증만
  이식하고 브랜치 폐기"로 결정까지 했지만 **실행은 안 됐다** — 다른 작업(비용
  절감 API 교체)으로 넘어가면서 미룸. **확인 완료: main의 `telegram_approval.py`는
  콜백의 `message_id`만 확인하고 `chat_id`는 확인 안 함** (2026-09-01 재확인,
  `_poll_for_decision` 함수). 실전 위험은 낮지만(다른 챗과 message_id가 우연히
  겹쳐야 함), 이론적 허점은 남아 있음. 다음 세션에서 처리할 것: (1) chat_id
  검증 이식 (`callback["message"]["chat"]["id"]`를 `TELEGRAM_CHAT_ID`와 비교),
  (2)
  `git worktree remove .worktrees/content-pipeline`, `git branch -d
  content-pipeline-implementation`, `git push origin --delete
  content-pipeline-implementation`으로 정리. **원격 브랜치 삭제는 되돌리기
  어려우니 실행 전 사용자에게 재확인.**
- `.claude/commands/handoff.md`, `.claude/commands/resume.md` 추가됨 — PC를
  옮길 때 `/handoff`로 이 문서들을 갱신·커밋·푸시하고, 다른 세션에서 `/resume`으로
  읽어들인다. **새로 만든 커맨드는 그 세션이 시작된 뒤에만 인식된다** — 세션
  중간에 추가했으면 새 세션을 열어야 보인다.
- `docs/testing-guide.md` 신규 추가 — "실제로 쇼츠 1편을 테스트 제작"하는
  이번 작업의 범위(YouTube 업로드 제외, 생성+조립까지)·사용 서비스·단계별
  체크리스트·텔레그램 승인 전 품질 체크리스트를 정리한 문서. ChatGPT 외부
  피드백을 검토해 반영/기각한 근거도 "외부 피드백 검토 기록" 절에 남겼다
  (analytics 피드백 루프·콘텐츠 스코어링·자동 QA는 이미 설계 문서 8절/
  `todo.md` "나중에"로 스코프 아웃된 항목이라 재론하지 않고, 체크포인트를
  1편 단위로 좁히는 것과 단계별 비용 리포트만 채택).
- **ffmpeg PATH 세션 문제 발견**: 사용자 PATH에는 `C:\Users\user\ffmpeg\
  ffmpeg-9.0.1-essentials_build\bin`이 영구 등록돼 있지만, 이 값이 등록되기
  *전에* 시작된 셸/세션은 인식하지 못한다. "터미널을 새로 열면 된다"는
  기존 메모가 맞지만, Claude Code 세션 자체가 오래 떠 있으면 재현될 수 있으니
  ffmpeg 관련 테스트가 이유 없이 skip되면 이것부터 의심할 것.

### 코드
모듈 11개 / 테스트 126건. 각 모듈은 한 가지만 한다.

| 모듈 | 역할 |
|---|---|
| `state.py` | `state/history.json` 읽기·쓰기. 네트워크 없음 |
| `llm.py` | Gemini 호출은 여기서만 (텍스트 생성, 무료 티어). 재시도 + JSON 펜스 제거 |
| `ideas.py` | 5축 아이디어 생성, 과거 조합 주입해 중복 회피 |
| `storyboard.py` | 샷 리스트·자막·SEO. 30초/4단계 검증 |
| `music.py` | 무드로 로컬 트랙 선택 |
| `image_gen.py` | Gemini Interactions API, 9:16 키프레임 |
| `video_gen.py` | MiniMax Hailuo first-last-frame |
| `assemble.py` | ffmpeg 조립. 네트워크 없음 |
| `telegram_approval.py` | 사람 승인 게이트 + 예산/체크포인트 가드 알림(`notify`) |
| `youtube_publish.py` | 업로드 + 합성 콘텐츠 신고 |
| `orchestrator.py` | 순서·돈·상태 기록만 결정 — 검증 예산/체크포인트 가드(`_validation_guard`), 이미지/영상 단계별 비용 콘솔 리포트(`=== COST REPORT ===`, 2026-09-01 추가)도 확인한다 |

### 외부 시스템 (저장소만 봐서는 알 수 없는 것)
- **YouTube 채널: 아직 안 만듦.** 설계상 신규 채널 생성이 전제다.
- **텔레그램 봇: 토큰·chat ID 확보 완료.** 아직 GitHub Secrets에는 미등록.
- **API 키 2종(Gemini/MiniMax): 발급 여부 미확인.**
- **GitHub Actions 시크릿 7종: 등록 안 됨.** (텔레그램 값 포함 전부 미등록)
- **`assets/music/`에 트랙 9개 등록 완료** (무드 5종). 렌더 가능한 상태.
- **워크플로는 한 번도 실행된 적 없다.**
- **Variables 3종(`VALIDATION_BUDGET_USD`/`VALIDATION_CHECKPOINT_EVERY`/
  `VALIDATION_ACK_COUNT`): 등록 안 됨.** 시크릿이 아니라 Variables라 없어도
  기본값(125 / 10 / 0)으로 동작한다 — 블로커 아님, 참고용.

### 비용 모델
| 항목 | 단가 | 영상 1편 |
|---|---|---|
| 키프레임 이미지 | $0.15/장 | 6~12장 |
| 영상 세그먼트 | $0.02/초 | 20~30초 |
| LLM | — | 무료 (Gemini 무료 티어) |

`orchestrator.estimate_cost()`가 **돈을 쓰기 전에** 견적을 내고
`MAX_COST_USD`(기본 5.0)를 넘으면 스토리보드를 최대 3회 다시 생성한다.
그래도 안 맞으면 한 푼도 쓰지 않고 그날 실행을 중단한다.

---

## 다음에 할 일

전부 사람이 브라우저·계정에서 해야 하는 일이다. 코드 작업은 없다.
**순서와 세부 절차는 `docs/testing-guide.md`에 체크리스트로 정리돼 있다 —
다음 세션은 그 문서의 미완료 항목부터 그대로 이어가면 된다.**

당장 다음(로컬 테스트 제작, YouTube 업로드는 아직 범위 밖):

1. **Gemini API 키 발급** — https://aistudio.google.com/apikey. 이미지 생성은
   유료라 연결된 Google Cloud 프로젝트에 결제 계정(카드) 등록 필요. **아직 미발급.**
2. **MiniMax API 키 발급 + 크레딧 충전** — https://www.minimax.io. **아직 미발급.**
3. 로컬 `.env` 구성(`VALIDATION_CHECKPOINT_EVERY=1` 포함) → 무료 아이디어
   스크리닝 → 개별 스모크 테스트(`llm`/`image_gen` 1장/`video_gen` 1개) →
   `run_pipeline()` 로컬 전체 실행 → 텔레그램 승인 체크리스트로 검토 후 거절
   (업로드 스킵) → `work/final.mp4` 확인.

그 다음(로컬 테스트가 만족스러울 때):

4. **YouTube 채널 생성 + OAuth 리프레시 토큰 1회 발급**
   Google Cloud Console에서 YouTube Data API v3를 켠 OAuth 클라이언트를 만들고,
   채널 계정으로 `google-auth-oauthlib` 로컬 서버 플로를 한 번 돌린다.
5. **저장소 시크릿 7종 등록** — Settings → Secrets and variables → Actions.
   목록은 `README.md` Setup 4번과 `.env.example`에 있다.
6. **Actions에서 수동 1회 실행** — Actions 탭 → "Daily Shorts Pipeline" →
   Run workflow. **스케줄에 맡기지 말고 반드시 지켜보면서 수동으로 먼저 돌릴 것**
   (이유는 아래 위험 1번).

---

## 진행 중이던 작업

없다. 이번 세션은 "실제로 쇼츠 1편을 테스트 제작"하는 절차를 문서화하고
(`docs/testing-guide.md`), 그 과정에서 나온 ChatGPT 외부 피드백을 검토해
저비용 항목 4가지(체크포인트 1편 단위, 단계별 비용 리포트, 텔레그램 승인
체크리스트, 무료 아이디어 스크리닝)를 반영한 뒤 끝났다. **Gemini/MiniMax API
키 발급은 아직 시작 전** — 다음 세션은 `docs/testing-guide.md` 1번부터
이어가면 된다.

---

## 알려진 위험 (다음 사람이 반드시 알아야 할 것)

### 1. 외부 API 스키마가 실제 키로 검증되지 않았다 — 가장 큰 위험
테스트 126건은 **전부 모킹**이다. 스키마가 틀려도 초록불이 뜬다.
구현 시점에 라이브 문서로 대조는 했지만, 문서와 실제가 또 다를 수 있다.

첫 유료 실행 전에 키 하나씩으로 스모크 테스트를 권한다:

```bash
PYTHONPATH=src GEMINI_API_KEY=... python -c \
  "from pipeline.image_gen import generate_image; print(generate_image('a rusty school bus', 'smoke.png'))"
```

영상 생성도 같은 식으로 이미지 2장을 만들어 `video_gen.generate_video_segment`에
넣어 본다. 여기서 깨지면 `_extract_image_data` / `_check_business_error`
근처의 응답 파싱만 고치면 된다.

텍스트 생성(`llm.py`)도 같은 이유로 검증이 안 됐다 — 별도로 돌려 본다:

```bash
PYTHONPATH=src GEMINI_API_KEY=... python -c \
  "from pipeline.llm import call_llm; print(call_llm('say hi in 3 words', system='be terse', max_tokens=64))"
```

여기서 깨지면 실패 양상이 두 가지다. 400 에러(`Unknown name` 같은 메시지)가 나면
라이브 API가 `thinking_config` 필드 자체를 모르는 것이니 `generation_config`에서
`thinking_config`를 빼고 재시도할 것. 빈 응답/텍스트 없음 에러가 나면 필드는
받아들여졌지만 무시돼 thinking이 예산을 다 먹은 것이니 `max_tokens`를 올릴 것.

### 2. GitHub Actions 사용시간
승인 대기가 **잡 안에서** 이뤄져 대기 시간 전부가 청구된다.
비공개 저장소 무료 한도는 월 2,000분.

- 생성 10~20분 + 승인 대기 최대 30분(`APPROVAL_TIMEOUT_SEC=1800`) → 하루 최대 50분
- 30일이면 최대 1,500분. 한도 안이지만 여유가 크지 않다.

대응 선택지 3가지는 `README.md`에 적어 뒀다. 그중 **저장소를 공개로 바꾸는 것**이
가장 간단하다 — 공개 저장소는 Actions 무제한이고, 시크릿은 저장소가 아니라
Actions Secrets에 있으므로 공개해도 노출되지 않는다. 다만 이 저장소를 공개하면
니치와 프롬프트가 그대로 드러난다는 점은 사용자가 판단할 문제다.

### 3. 미해결로 남긴 것
- **음악 중복 회피 없음.** `pick_music`에 `used_recently`를 넘기지 않아 같은
  트랙이 연달아 쓰일 수 있다. 상태 스키마에 트랙 이력이 없어서 별건이다.
- **실패 시 알림 없음.** 파이프라인이 중간에 죽으면 Actions 로그에만 남는다.
  텔레그램으로 실패도 알리면 좋다.

---

## 최근에 알게 된 것 (같은 삽질 반복 금지)

**계획서에 적힌 외부 API 형태를 믿지 말 것.** 이번에 구현하면서 계획서가
틀린 곳이 여러 군데 나왔고, 그대로 옮겼다면 첫 실행에서 죽었다.

- **Gemini 이미지**: 계획서의 `/v1beta/models/{id}:generateContent` +
  `contents/parts/inlineData`는 구버전이다. 현행은 `/v1beta/interactions` +
  `model`/`input`/`response_format`, 응답은 `steps[].content[]` 중
  `type=="image"`의 `data`. 인증은 `?key=`가 아니라 `x-goog-api-key` 헤더.
  구버전엔 **종횡비 옵션이 아예 없어서** 세로 9:16 쇼츠에는 마이그레이션이 필수였다.
- **MiniMax**: 호스트가 `api.minimax.chat`이 아니라 **`api.minimax.io`**.
  `first_frame_image`는 맨 base64가 아니라 **Data URI**.
  실패가 **HTTP 200 안의 `base_resp.status_code`**로 온다(잔액부족 1008 등) —
  HTTP 코드만 보면 성공으로 보인다. duration은 6/10초만 받는다.
- **ffmpeg drawtext는 `fontfile=` 없이 윈도우에서 무조건 실패한다**
  ("Fontconfig error: Cannot load default config file"). CI 러너도
  `fonts-dejavu-core`를 따로 깔아야 한다. 자막은 `text=` 대신 **`textfile=`**로
  넘겨 콤마·콜론 이스케이프를 통째로 피하고, **`expansion=none`**을 붙여야
  `%`를 strftime으로 해석해 죽는 걸 막는다(실측). 필터 인자 안의 `C:`는
  `C\:`로 이스케이프한다 — `-i` 경로는 argv라 불필요.
- **`-shortest`만 쓰면 음악이 영상보다 짧을 때 영상이 잘린다.**
  음악 입력에 `-stream_loop -1`.
- **`pytest.ini`의 `pythonpath = src`는 pytest 전용이다.** 워크플로의
  `python -m pipeline.orchestrator`는 `PYTHONPATH=src` 없이 즉사한다.
  테스트로는 절대 안 잡히고 첫 스케줄 실행 날에 드러난다.
- **모킹 테스트는 변이 테스트로 검증할 것.** 계획서 원본 코드로 되돌렸을 때
  실제로 빨간불이 되는지 확인하면 헛도는 테스트를 거를 수 있다. Task 8·9에서
  이 방법으로 테스트가 실제 의미가 있는지 확인했다.

### 로컬 개발 환경
- ffmpeg는 `winget install Gyan.FFmpeg`로 깐다. **설치 후 터미널을 새로 열어야**
  PATH가 잡힌다. 없으면 조립 테스트 10건이 이유를 붙여 skip된다.
- Ubuntu는 `sudo apt-get install -y ffmpeg fonts-dejavu-core` — 폰트를 빼면 안 된다.
