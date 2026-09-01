# Shorts

AI 쇼츠 자동 생성 시스템 (수익화 목적).

매일 1회 GitHub Actions가 "특별한 장소에 집짓기" 쇼츠를 한 편 만들고,
텔레그램으로 미리보기를 보내 1탭 승인을 받은 뒤 YouTube에 올린다.

- 설계 문서: [docs/superpowers/specs/2026-08-31-ai-shorts-content-pipeline-design.md](docs/superpowers/specs/2026-08-31-ai-shorts-content-pipeline-design.md)
- 구현 계획: [docs/superpowers/plans/2026-08-31-ai-shorts-content-pipeline-implementation.md](docs/superpowers/plans/2026-08-31-ai-shorts-content-pipeline-implementation.md)

## 파이프라인

```
아이디어(5축) → 스토리보드 → 예산 게이트 → 키프레임 이미지 → 영상 세그먼트
  → ffmpeg 조립(켄번즈·자막·음악) → 텔레그램 승인 → YouTube 업로드 → 상태 커밋
```

각 모듈은 하나씩만 담당한다. `state.py`는 네트워크를 모르고, `llm.py`만 Anthropic을
호출하며, `assemble.py`는 ffmpeg만 돌린다. `orchestrator.py`에는 자체 로직이 없다 —
순서와 돈과 상태 기록만 결정한다.

## 로컬 개발

```bash
python -m pip install -r requirements.txt
python -m pytest
```

ffmpeg/ffprobe가 PATH에 있어야 조립 테스트가 돈다. 없으면 해당 테스트는
이유를 붙여 skip된다.

- Windows: `winget install Gyan.FFmpeg` (설치 후 터미널을 새로 열어야 PATH가 잡힌다)
- Ubuntu: `sudo apt-get install -y ffmpeg fonts-dejavu-core`

## Setup

1. **음악 트랙 채우기** — `assets/music/README.md` 참조.
   YouTube 오디오 라이브러리는 공개 API가 없어 수동 다운로드가 필요하다.
   **트랙이 없으면 파이프라인이 영상을 만들지 못한다.**

2. **YouTube OAuth 리프레시 토큰 1회 발급** — Google Cloud Console에서
   YouTube Data API v3를 켠 OAuth 클라이언트를 만들고, 채널 계정으로
   `google-auth-oauthlib`의 로컬 서버 플로를 한 번 돌려 리프레시 토큰을 얻는다.
   이 동의 절차만 수동이고, 이후 사용은 자동이다.

3. **텔레그램 봇 만들기** — [@BotFather](https://t.me/BotFather)로 봇을 만들어
   `TELEGRAM_BOT_TOKEN`을 얻고, 봇에게 아무 메시지나 보낸 뒤 `getUpdates`로
   숫자 `TELEGRAM_CHAT_ID`를 확인한다.

4. **저장소 시크릿 등록** — Settings → Secrets and variables → Actions:
   `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MINIMAX_API_KEY`,
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.

5. **첫 실행은 반드시 수동으로** — Actions 탭 → "Daily Shorts Pipeline" →
   Run workflow. 외부 API 스키마가 실제와 맞는지는 실제 키로 한 번 돌려 봐야
   확인된다(아래 "알려진 위험" 참조).

워크플로는 매일 14:00 UTC에 돈다. 시각은 `.github/workflows/daily-shorts.yml`의
cron에서 바꾼다.

## 비용

| 항목 | 단가 | 영상 1편 |
|---|---|---|
| 키프레임 이미지 | $0.15/장 | 6~12장 |
| 영상 세그먼트 | $0.02/초 | 20~30초 |
| LLM(아이디어+스토리보드) | — | 약 $0.07 |
| 음악 | 무료 | — |

목표 원가는 편당 **$3~5**다. `orchestrator.estimate_cost()`가 **돈을 쓰기 전에**
견적을 내고, `MAX_COST_USD`(기본 5.0)를 넘으면 스토리보드를 다시 생성한다.
3회 안에 예산에 못 맞추면 한 푼도 쓰지 않고 그날 실행을 중단한다.

### GitHub Actions 사용시간 주의

파이프라인은 텔레그램 승인을 **잡 안에서 기다린다.** 그 대기 시간이 전부
Actions 사용시간으로 청구된다. 비공개 저장소 무료 한도는 월 2,000분이다.

- 생성 약 10~20분 + 승인 대기 최대 30분(`APPROVAL_TIMEOUT_SEC=1800`) → 하루 최대 50분
- 30일이면 최대 1,500분. 한도 안이지만 여유가 많지는 않다.

승인을 자주 늦게 누르면 한도를 넘길 수 있다. 대응 선택지:

- `APPROVAL_TIMEOUT_SEC`를 더 줄인다 (타임아웃되면 게시하지 않는다 — 제작비는 나간다)
- 저장소를 공개로 바꾼다 (공개 저장소는 Actions 무료 무제한. 시크릿은 저장소가 아니라
  Actions Secrets에 있으므로 공개해도 노출되지 않는다)
- 생성과 승인을 두 워크플로로 분리한다 (승인 대기를 잡 밖으로 뺀다)

## 정책

이 채널의 영상은 실재하는 장소에 실재하지 않는 건축물을 짓는 내용이므로,
YouTube의 "변경되거나 합성된 콘텐츠" 공개 대상에 해당한다.
`youtube_publish.py`는 항상 `status.containsSyntheticMedia=true`로 업로드한다.
신고하지 않으면 YouTube가 임의로 라벨을 붙이거나(제거 불가) 광고 수익을 뺄 수 있다.

5축 변형 시스템(장소·컨셉·훅·비주얼·오디오)은 단순한 다양성 장치가 아니라,
2026년 강화된 "inauthentic content" 정책에서 템플릿 대량생산으로 분류되지 않기
위한 장치다. 과거 조합은 `state/history.json`에 남고 다음 프롬프트에 주입된다.

## 검증 단계 예산 관리

수익화가 검증되지 않은 상태에서 영상당 $3~5씩 무한정 나가는 걸 막기 위해,
`orchestrator.py`가 매일 실행 전에 두 가지를 확인한다.

- 누적 지출이 `VALIDATION_BUDGET_USD`(기본 $125)에 도달하면 그날 실행을 거부한다.
  이 검사는 그날 실행분을 쓰기 *전에* 하므로, 실제 총액은 예산보다 영상 한 편
  분량(약 $3~5)만큼 더 나갈 수 있다.
- 마지막 검토 이후 `VALIDATION_CHECKPOINT_EVERY`(기본 10)편이 또 쌓이면 실행을
  거부한다. `VALIDATION_ACK_COUNT`(기본 0)를 검토한 영상 수로 올려야 재개된다.

두 경우 다 텔레그램으로 알림이 오고, 아무 비용도 쓰지 않은 채 멈춘다. 값은
저장소 Settings → Secrets and variables → Actions → **Variables** 탭에서
설정한다 (시크릿이 아니라 Variables인 이유: `VALIDATION_ACK_COUNT`는 체크포인트마다
사람이 직접 바꿔야 하는 값이라, 코드/워크플로 수정 없이 화면에서 바로 바꿀 수 있어야
한다). 아직 설정하지 않았다면 기본값(125 / 10 / 0)으로 동작한다.

체크포인트 검사는 `VALIDATION_CHECKPOINT_EVERY`를 `0`으로 둔다고 꺼지지 않는다
— 오히려 매번 막힌다. 검사를 사실상 끄려면 아주 큰 값(예: `100000`)을 넣을 것.

## 알려진 위험

- **외부 API 스키마는 실제 키로 검증되지 않았다.** 모든 테스트는 모킹이라
  스키마가 틀려도 초록불이 뜬다. Gemini(이미지)와 MiniMax(영상)는 구현 시점에
  라이브 문서로 대조했지만, 첫 유료 실행 전에 키 1개씩으로 스모크 테스트를
  한 번 돌려 보는 것을 강력히 권한다.
- 음악 트랙 중복 회피가 없다. 같은 트랙이 연달아 쓰일 수 있다.
