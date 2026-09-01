# 할 일

완료하면 `[x]`로 바꾸고 **무엇을 어떻게 확인했는지**를 함께 남긴다.
현재 상황 전체는 `docs/STATE.md`를 본다.

---

## 코드 (완료)

- [x] **v1 콘텐츠 생성 파이프라인 구현 — 계획서 Task 1~13 전부**
  2026-09-01 완료. 모듈 11개, 테스트 126건 전부 통과(`python -m pytest`, ffmpeg 9.0.1).
  진입점 임포트(`PYTHONPATH=src python -c "import pipeline.orchestrator"`)와
  워크플로 YAML 파싱까지 확인. `main`에 머지·푸시, 구현 브랜치·워크트리 정리 완료.
  계획서 대비 수정한 곳은 각 Task 커밋 메시지에 이유를 남겼다.

- [x] **계획서의 외부 API 스키마 오류 수정**
  Gemini는 구버전 generateContent → Interactions API로 재작성(세로 9:16 지정이
  구버전엔 아예 없었음). MiniMax는 호스트·Data URI·base_resp 처리 수정.
  각각 라이브 문서로 대조해 확인. Task 8·9는 계획서 원본 코드로 되돌리면
  테스트가 실제로 빨간불이 되는 것까지 확인(변이 테스트).

- [x] **지출 전 예산 게이트 추가**
  계획서엔 비용 기록만 있고 상한이 없었다. `estimate_cost()` + `MAX_COST_USD`로
  돈 쓰기 전에 막는다. 예산 초과 스토리보드로 `image_gen`이 한 번도 호출되지
  않는 것을 테스트로 확인.

- [x] **검증 예산 가드 + 체크포인트 일시정지 추가**
  2026-09-01 완료. 누적 지출 $125 또는 검토 후 10편 초과 시 파이프라인이 스스로
  멈추고 텔레그램으로 알린다(`orchestrator._validation_guard` + `telegram_approval.notify`).
  `python -m pytest`로 신규 테스트 포함 전체 통과 확인. 스펙:
  `docs/superpowers/specs/2026-09-01-validation-budget-guard-design.md`.

- [x] **LLM 제공자 교체 — Anthropic → Gemini 무료 티어**
  2026-09-01 완료. `llm.py`를 Anthropic SDK에서 Gemini Interactions API로
  재작성(`call_llm` 시그니처는 그대로라 `ideas.py`/`storyboard.py` 무변경).
  Anthropic 패키지·시크릿 완전 제거(8종→7종). 통합 리뷰 2라운드에서 실제
  위험(Gemini Flash 기본 thinking이 토큰 예산을 다 먹는 문제 등) 발견해
  `thinking_config.thinking_budget=0` 반영. `python -m pytest` 126건 전부
  통과 확인. **실제 키로는 아직 검증 안 됨 — 스모크 테스트 필수 (아래 5번).**
  스펙: `docs/superpowers/specs/2026-09-01-llm-gemini-free-tier-design.md`.

- [x] **`/handoff`, `/resume` 커스텀 슬래시 커맨드 추가**
  2026-09-01 완료. `.claude/commands/`에 저장, PC 간 인수인계를 자동화.
  `/handoff`로 STATE.md/todo.md 갱신+커밋+푸시, `/resume`으로 다른 세션에서
  읽어들임. **세션 도중 추가한 커맨드는 새 세션을 열어야 인식됨** (실측).

- [x] **테스트 제작 가이드 작성 + 단계별 비용 리포트 추가**
  2026-09-01 완료. `docs/testing-guide.md`에 "실제 쇼츠 1편 테스트 제작"
  범위(YouTube 업로드 제외)·사용 서비스·단계별 체크리스트·텔레그램 승인
  체크리스트를 정리. ChatGPT 외부 피드백을 검토해 analytics 피드백 루프·
  콘텐츠 스코어링·자동 QA는 이미 설계 문서 8절/이 파일의 "나중에" 섹션으로
  스코프 아웃된 항목이라 재론하지 않고, 저비용 항목 4가지(체크포인트 1편
  단위, 단계별 비용 리포트, 승인 체크리스트, 무료 아이디어 스크리닝)만 채택.
  `orchestrator.py`에 이미지/영상 비용을 분리해 `=== COST REPORT ===`로
  콘솔에 찍고 `state/history.json`의 `breakdown`에도 남기도록 수정.
  `python -m pytest` 126건(ffmpeg 포함) 전부 통과로 확인.

---

## 반복 작업 (일회성 아님)

- [ ] **체크포인트마다(약 10편) YouTube Studio 확인 후 `VALIDATION_ACK_COUNT` 올리기**
  안 하면 파이프라인이 오류 없이 조용히 멈춘다 — 텔레그램 알림과 Actions
  요약 화면의 `::warning::` 줄이 유일한 신호다. 자세한 내용은 README.md
  "검증 단계 예산 관리".

## 사용자 수동 작업 (남은 전부)

- [x] **1. `assets/music/`에 트랙 8~10개 채우기**
  2026-09-01 완료. 저작자 표시 필요 없는 트랙 9개, 무드 5종(tense and
  driving/upbeat/romantic/inspirational/eerie)으로 등록. `manifest.json`의
  모든 파일 경로가 실제로 존재하는지 스크립트로 확인함.

- [ ] **2. YouTube 채널 생성 + OAuth 리프레시 토큰 발급**
  Google Cloud Console에서 YouTube Data API v3 활성화 → OAuth 클라이언트 생성
  → 채널 계정으로 `google-auth-oauthlib` 로컬 서버 플로 1회.
  동의 절차만 수동이고 이후는 자동.

- [x] **3. 텔레그램 봇 생성**
  2026-09-01 완료. @BotFather로 봇 생성해 `TELEGRAM_BOT_TOKEN` 확보,
  `getUpdates`로 `TELEGRAM_CHAT_ID` 확인함. 아직 GitHub Secrets에는 미등록
  (아래 4번에서 등록).

- [ ] **4. GitHub Actions 시크릿 7종 등록**
  Settings → Secrets and variables → Actions.
  `GEMINI_API_KEY`, `MINIMAX_API_KEY`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
  텔레그램 값은 이미 확보됨. Gemini/MiniMax 키는 발급 여부 미확인 —
  결제(선불 크레딧) 필요.

- [ ] **5. 스모크 테스트 후 수동 1회 실행** ← 첫 유료 실행 전 필수
  테스트가 전부 모킹이라 API 스키마 오류를 못 잡는다. 키 하나씩으로
  `image_gen.generate_image` / `video_gen.generate_video_segment` / `llm.call_llm`을
  먼저 돌려 보고, 그 다음 Actions 탭에서 "Daily Shorts Pipeline" → Run workflow.
  스케줄에 맡기지 말고 지켜보면서 돌릴 것. 명령 예시는 `docs/STATE.md` 위험 1번.
  `llm.call_llm`의 `thinking_config` 필드는 특히 처음 검증되는 것이라 주의.

---

## 결정 대기

- [ ] **저장소를 공개로 전환할지**
  공개 저장소는 Actions 사용시간 무제한이라 승인 대기 비용 문제가 사라진다.
  시크릿은 저장소가 아니라 Actions Secrets에 있어 노출되지 않는다.
  다만 니치와 프롬프트가 그대로 드러난다. 판단 필요.
  대안은 `APPROVAL_TIMEOUT_SEC` 축소 또는 워크플로 2단 분리.

---

## 나중에 (v1 안정화 후)

- [ ] 음악 트랙 중복 회피 — 상태 스키마에 트랙 이력 추가 후 `used_recently` 연결
- [ ] 파이프라인 실패 시 텔레그램 알림 (지금은 Actions 로그에만 남는다)
- [ ] `origin/content-pipeline-implementation` 브랜치 정리 — 내용 확인 완료
      (다른 세션의 독립 구현, chat_id 검증만 유의미한 차이점). 텔레그램
      chat_id 검증 이식 + 브랜치/워크트리 삭제. 자세한 내용은
      `docs/STATE.md` "저장소" 섹션.
- [ ] 설계 문서 8절의 스코프 아웃 항목들 — 트렌드 주제 추천 엔진,
      링크 기반 유사주제 생성기, 멀티플랫폼 확장, 성과 분석 루프,
      AI 내레이터 캐릭터(v2)
