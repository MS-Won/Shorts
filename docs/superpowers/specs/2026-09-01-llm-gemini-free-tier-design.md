# LLM 제공자 교체: Anthropic → Gemini 무료 티어

- 작성일: 2026-09-01
- 상태: 승인됨

## 1. 배경 및 목적

파이프라인은 아이디어(5축) 생성과 스토리보드/스크립트 생성 두 곳에서 LLM을 호출한다 (`src/pipeline/llm.py`의 `call_llm`을 통해서만, `ideas.py`/`storyboard.py`가 이를 소비). 지금은 Anthropic Claude API를 쓰는데, Anthropic API는 영구 무료 티어가 없어 선불 크레딧 결제가 필요하다.

리서치 결과, Google Gemini API는 Flash 계열 모델에 **영구 무료 티어**(분당 15회, 하루 100만 토큰, 신용카드 불필요)를 제공한다. 이 파이프라인의 LLM 호출량(하루 1~수 회, 예산 초과 시 스토리보드 최대 3회 재시도)은 이 한도에 전혀 걸리지 않는다. 또한 `GEMINI_API_KEY`는 이미 `image_gen.py`가 이미지 생성에 쓰고 있어 **새 시크릿 없이 재사용** 가능하다.

목적: Anthropic 의존성을 완전히 제거하고 Gemini 무료 티어로 대체해, 영상당 LLM 비용(~$0.07)과 별도 API 키 관리 부담을 없앤다.

## 2. 근거: 기존에 검증된 API 패턴 재사용

`image_gen.py`는 이미 Gemini의 **Interactions API**(`https://generativelanguage.googleapis.com/v1beta/interactions`, `x-goog-api-key` 헤더 인증, `input`/`response_format` 요청 형태, `steps[].content[]` 응답 형태)를 실사용 검증까지 마친 상태다 (구버전 `models/{id}:generateContent` 형태는 레거시라 코드 주석에도 명시돼 있음).

리서치로 확인: 이 API는 `response_format: {"type": "text"}`로 순수 텍스트 출력도 지원한다. 따라서 `llm.py`도 같은 엔드포인트·인증·응답 파싱 패턴을 그대로 따라가면, 이미 검증된 경로를 재사용하는 셈이라 "계획서의 API 스펙이 실제와 달랐다"는 이 프로젝트가 두 번 겪은 함정을 피할 수 있다.

## 3. 변경 사항

### 3.1 `src/pipeline/llm.py` 재작성
- `anthropic` SDK 제거, `requests`로 직접 Interactions API 호출 (`image_gen.py`와 동일한 요청/인증 방식)
- 모델: `GEMINI_TEXT_MODEL` 환경변수, 기본값 `gemini-flash-latest` (최신 안정 Flash 모델을 자동으로 가리키는 별칭 — 모델 교체 시 코드 수정 불필요)
- 응답 파싱: `image_gen.py`의 `_extract_image_data`를 미러링해 `steps[].content[]`에서 `type == "text"`인 항목의 텍스트를 추출
- 재시도/백오프 로직(지수 백오프, `retries`회)은 기존과 동일하게 유지

### 3.2 인터페이스는 완전히 동일하게 유지
```python
call_llm(prompt: str, system: str | None = None, max_tokens: int = 1024, retries: int = 3) -> str
```
이 시그니처와 동작(성공 시 텍스트 반환, 실패 시 `LLMError`)이 그대로 유지되므로 **`ideas.py`, `storyboard.py`는 코드 변경이 전혀 필요 없다.**

### 3.3 Anthropic 완전 제거
- `requirements.txt`: `anthropic` 패키지 제거
- `.env.example`, `README.md` Setup 섹션: `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` 항목 제거
- `.github/workflows/daily-shorts.yml`: `ANTHROPIC_API_KEY` secret 참조 제거
- `src/pipeline/orchestrator.py`의 `_REQUIRED_ENV_VARS`(사전점검 목록): `ANTHROPIC_API_KEY` 제거 (`GEMINI_API_KEY`는 이미 포함돼 있어 추가 불필요)
- `docs/STATE.md`, `CLAUDE.md`, `todo.md`: Anthropic 관련 서술을 Gemini로 갱신, GitHub Actions 시크릿 목록도 7종으로 갱신

## 4. 테스트

`tests/test_llm.py`의 기존 구조(성공/재시도/실패 케이스, 모킹된 응답)를 유지하되 모킹 대상을 `pipeline.llm.requests.post`로 변경한다. 실제 네트워크 호출은 하지 않는다. `image_gen.py`의 기존 테스트 패턴(`tests/test_image_gen.py`)을 참고해 일관된 스타일을 따른다.

## 5. 범위 밖

- Interactions API의 JSON 스키마 강제 출력 기능(`response_format`에 `schema` 추가) — `ideas.py`/`storyboard.py`의 현재 파싱+재시도 로직을 바꿔야 하는 별개의 개선이라 이번 범위에서 제외한다. 현재 방식도 이미 검증돼 있다 (YAGNI).
- 이미지 생성(Gemini 유료) → Cloudflare Workers AI 무료 티어 교체 — 별도 브레인스토밍으로 다룬다.
