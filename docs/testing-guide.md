# 첫 테스트 제작 가이드

> 이 문서는 "실제로 쇼츠 1편을 테스트 제작"하는 이번 작업 세션의 범위와
> 사용하는 외부 프로그램/서비스를 정리한 것이다. 진행 상황은 아래 체크리스트에
> 갱신한다. 프로젝트 전체 상태는 `docs/STATE.md`, 작업 큐는 `todo.md` 참조.

**작성일**: 2026-09-01

---

## 지금 하려는 것

파이프라인 코드는 완성됐지만 실제 키로 한 번도 돌려본 적이 없다
(`docs/STATE.md` "알려진 위험 1번"). 이번 세션 목표는:

**이미지·영상 생성 → ffmpeg 조립까지 로컬에서 실제로 돌려 결과물(mp4)을 확인한다.**

- YouTube 업로드는 이번 범위에 **포함하지 않는다** — 채널·OAuth가 아직 없고
  (`todo.md` 항목 2), 텔레그램 승인 단계에서 거절하면 `youtube_publish`가
  호출되지 않으므로 업로드 없이도 끝까지 테스트 가능하다.
- 비용은 실제로 발생한다 (영상 1편 약 $3~5, 예산 게이트는 `MAX_COST_USD` 기본 5.0).

---

## 사용하는 프로그램·서비스

| 서비스 | 역할 | 이번 테스트에 필요? | 현재 상태 |
|---|---|---|---|
| **Google AI Studio (Gemini API)** | 아이디어·스토리보드 텍스트 생성(무료 티어), 키프레임 이미지 생성(유료) | ✅ 필수 | 키 미발급 |
| **MiniMax (Hailuo)** | 첫-마지막 프레임 기반 영상 세그먼트 생성(유료) | ✅ 필수 | 키 미발급 |
| **Telegram Bot (@BotFather)** | 완성 영상 미리보기 + 1탭 승인/거절 | ✅ 필수 (거절해서 업로드 스킵) | 토큰·chat ID 확보 완료, 로컬 `.env`엔 미등록 |
| **ffmpeg / ffprobe** | 켄번즈 팬·자막·음악 합성 로컬 조립 | ✅ 필수 | 로컬 설치 완료 (winget) |
| **YouTube Data API v3 (OAuth)** | 완성 영상 업로드 | ❌ 이번 범위 밖 | 채널 미생성, 토큰 미발급 |
| **GitHub Actions** | 매일 자동 실행 | ❌ 이번 범위 밖 (로컬 실행으로 대체) | 시크릿 미등록, 실행 이력 없음 |

### 참고 링크

- Gemini API 키 발급: https://aistudio.google.com/apikey
- MiniMax 콘솔: https://www.minimax.io (구버전 문서의 `api.minimax.chat`이 아니라
  현재는 `api.minimax.io` — `docs/STATE.md` "최근에 알게 된 것" 참조)
- Telegram BotFather: https://t.me/BotFather

---

## 단계별 체크리스트

- [ ] **1. Gemini API 키 발급**
  https://aistudio.google.com/apikey 에서 발급. 이미지 생성(`gemini-3-pro-image`)은
  유료라 연결된 Google Cloud 프로젝트에 결제 계정(카드) 등록 필요.

- [ ] **2. MiniMax API 키 발급 + 크레딧 충전**
  https://www.minimax.io 가입 → 콘솔에서 키 발급 → 선불 크레딧 충전.
  영상 세그먼트 단가 $0.02/초, 20~30초 기준 세그먼트당 약 $0.4~0.6.

- [ ] **3. 로컬 `.env` 구성**
  `.env.example`을 복사해 `GEMINI_API_KEY`, `MINIMAX_API_KEY`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`(이미 확보된 값) 채우기.
  `.gitignore`에 `.env`가 포함돼 있는지 확인 후 진행 (커밋 금지).
  **`VALIDATION_CHECKPOINT_EVERY=1`도 같이 넣는다** — 기본값(10)이 아니라
  1로 두면 영상 1편이 나올 때마다 사람이 검토하고 `VALIDATION_ACK_COUNT`를
  올려야 다음 실행이 풀린다. 검증 초기 단계의 위험비용을 편당으로 제한하는
  용도 (ChatGPT 피드백의 "Gate" 개념 — 코드는 이미 이 값을 지원하므로 값만
  바꾸면 된다).

- [ ] **4. 무료 아이디어 스크리닝** (돈 쓰기 전 마지막 필터)
  `ideas.generate_idea()`/`storyboard.generate_storyboard()`는 Gemini
  텍스트 무료 티어라 비용이 없다. 스토리보드를 2~3개 뽑아서 사람이 눈으로
  보고 "이걸 실제로 만들 가치가 있는가"를 판단한 뒤, 가장 나은 하나로 5번
  전체 실행을 진행한다. **오늘 1회성 수동 확인이며 상시 자동화는 아니다** —
  설계상 5축 변형 시스템은 매일 무인 실행이 전제라, 상시 사람이 아이디어를
  고르는 건 방향과 어긋난다.

- [ ] **5. 개별 스모크 테스트** (전체 실행 전 스키마 오류를 싸게 걸러내기 위함)
  `docs/STATE.md` "알려진 위험 1번"의 명령으로 하나씩:
  1. `pipeline.llm.call_llm` (무료)
  2. `pipeline.image_gen.generate_image` (건당 $0.15) — **이미지 1장만** 만들어서
     품질을 확인한다. 전체 스토리보드(6~12장)를 한 번에 만들지 않는다.
  3. `pipeline.video_gen.generate_video_segment` (초당 $0.02, 이미지 2장 필요) —
     **영상 세그먼트 1개만** 만들어서 움직임·일관성·첫/마지막 프레임을 확인한다.

- [ ] **6. `run_pipeline()` 로컬 전체 실행**
  `PYTHONPATH=src python -m pipeline.orchestrator` (ffmpeg를 PATH에서 인식하는
  새 터미널에서 실행할 것). 실행이 끝나면 콘솔에 `=== COST REPORT ===`로
  이미지/영상 단계별 비용이 찍힌다 (오늘 추가한 기능). 텔레그램으로
  미리보기가 오면 아래 체크리스트로 검토한 뒤 **거절**해서 YouTube 업로드
  단계를 건너뛴다. `work/final.mp4` 결과물도 직접 재생해서 확인한다.

  **승인 전 체크리스트**:
  - [ ] 첫 2초에 이탈할 이유가 없는가?
  - [ ] 영상 내용이 이해되는가?
  - [ ] 화면이 깨지거나 아티팩트가 없는가?
  - [ ] 자막 오류·잘림이 없는가?
  - [ ] 음악 음량이 나레이션/자막을 방해하지 않는가?
  - [ ] 마지막에 payoff(마무리)가 있는가?
  - [ ] AI 생성물 티가 지나치게 강하지 않은가?
  - [ ] 이 포맷을 반복 제작할 가치가 있는가?

- [ ] **7. 결과 검토 후 다음 단계 결정**
  영상 품질·비용이 만족스러우면 YouTube 채널 생성 + OAuth 발급(`todo.md` 항목 2)으로
  넘어가 실제 업로드까지 테스트. 이후 확장은 1편 → 3편 → 10편 순으로 늘려가며
  `VALIDATION_CHECKPOINT_EVERY`를 단계적으로 올린다 — 처음부터 자동화(GitHub
  Actions 매일 실행)로 바로 가지 않는다.

---

## 주의할 것

- `run_pipeline()`은 돈을 쓴다 — 함부로 여러 번 돌리지 않는다 (`CLAUDE.md`).
- `assets/music/`에 트랙이 없으면 `pick_music`이 `NoMusicAvailableError`를
  던진다 — 이미 9개 등록돼 있어 이번 테스트는 문제없음.
- 스모크 테스트에서 400 에러/빈 응답이 나면 `docs/STATE.md` "알려진 위험 1번"의
  대응법(thinking_config 제거 또는 max_tokens 상향) 참조.
- **ffmpeg가 사용자 PATH에는 영구 등록돼 있지만(`C:\Users\user\ffmpeg\...\bin`),
  Claude Code 세션이 그 갱신 이전에 시작됐으면 인식을 못 한다** (2026-09-01
  확인). 6번 전체 실행 전에 새 터미널을 열 것.

---

## 외부 피드백 검토 기록

ChatGPT가 이 가이드 초안에 "기술 검증 계획일 뿐 수익화 검증 계획이 아니다"는
피드백을 줬다 (자동 QA, 콘텐츠 스코어링, analytics 피드백 루프, 포맷 학습 등
제안). 검토 결과:

- **analytics 피드백 루프·콘텐츠 스코어링·자동 QA 서브시스템**: 새로운
  지적이 아니라 설계 문서 8절과 `todo.md` "나중에" 섹션의 "성과 분석 루프"로
  이미 v2 스코프 아웃된 항목. v1이 데이터를 쌓기 전에는 설계할 근거가 없어
  채택하지 않음.
- **단계별 비용 Gate($5→$20~30→$50~100→$100+)**: 이미 `VALIDATION_BUDGET_USD` +
  `VALIDATION_CHECKPOINT_EVERY`로 구현돼 있던 개념. 새 코드 대신 값 조정만
  반영 (위 3번).
- **채택한 것 4가지** (저비용·기존 계획과 충돌 없음): 체크포인트 1편 단위로
  축소, 단계별 비용 콘솔 리포트(`orchestrator.py`에 반영, 2026-09-01), 텔레그램
  승인 체크리스트, 돈 쓰기 전 무료 아이디어 스크리닝 1회.
