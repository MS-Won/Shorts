# 할 일

완료하면 `[x]`로 바꾸고 **무엇을 어떻게 확인했는지**를 함께 남긴다.
현재 상황 전체는 `docs/STATE.md`를 본다.

---

## 코드 (완료)

- [x] **v1 콘텐츠 생성 파이프라인 구현 — 계획서 Task 1~13 전부**
  2026-09-01 완료. 모듈 11개, 테스트 117건 전부 통과(`python -m pytest`, ffmpeg 9.0.1).
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

- [ ] **3. 텔레그램 봇 생성**
  @BotFather로 봇 생성 → `TELEGRAM_BOT_TOKEN`.
  봇에게 메시지 1회 전송 후 `getUpdates`로 숫자 `TELEGRAM_CHAT_ID` 확인.

- [ ] **4. GitHub Actions 시크릿 7종 등록**
  Settings → Secrets and variables → Actions.
  `GEMINI_API_KEY`, `MINIMAX_API_KEY`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.

- [ ] **5. 스모크 테스트 후 수동 1회 실행** ← 첫 유료 실행 전 필수
  테스트가 전부 모킹이라 API 스키마 오류를 못 잡는다. 키 하나씩으로
  `image_gen.generate_image` / `video_gen.generate_video_segment` / `llm.call_llm`을
  먼저 돌려 보고, 그 다음 Actions 탭에서 "Daily Shorts Pipeline" → Run workflow.
  스케줄에 맡기지 말고 지켜보면서 돌릴 것. 명령 예시는 `docs/STATE.md` 위험 1번.

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
- [ ] `origin/content-pipeline-implementation` 브랜치 내용 확인 후 정리 (미확인 상태)
- [ ] 설계 문서 8절의 스코프 아웃 항목들 — 트렌드 주제 추천 엔진,
      링크 기반 유사주제 생성기, 멀티플랫폼 확장, 성과 분석 루프,
      AI 내레이터 캐릭터(v2)
