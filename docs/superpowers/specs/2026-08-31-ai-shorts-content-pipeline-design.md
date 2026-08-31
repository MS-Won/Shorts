# AI 쇼츠 자동 생성 시스템 — v1: 콘텐츠 생성 파이프라인 설계

- 작성일: 2026-08-31
- 상태: 승인됨 (v1 범위 확정, 상세 구현 계획은 별도 writing-plans 산출물에서 다룸)

## 1. 배경 및 목적

목적은 **수익화 가능한 쇼츠(Shorts) 자동 생성 시스템** 구축이다. 성공 기준은 다음 세 가지다.

1. 가장 빠르게 수익화될 수 있을 것
2. 운영자(사용자)의 수작업 개입이 최소화될 것
3. 장기적으로 꾸준히 유지 가능할 것 (플랫폼 정책 위반으로 채널이 정지되지 않을 것)

주제 선정은 원래 두 가지 방법으로 구상되었다: (1) 트렌드를 자동 분석해 가장 수익화가 잘 되는 주제를 추천받는 시스템, (2) 예시 링크를 보고 비슷한 주제를 자동 생성하는 시스템. 이 두 가지는 범용 "주제 추천 엔진"으로서 **별도 서브프로젝트**로 분리하고, 이번 v1에서는 이미 리서치로 검증된 단일 니치(아래 3절)에 대해 파이프라인 자체를 먼저 완성한다.

## 2. 프로젝트 분해 및 우선순위

전체 시스템은 다음 5개의 독립 서브시스템으로 분해된다.

1. **콘텐츠 생성 파이프라인** ← 이번 v1의 범위
2. 트렌드 분석/주제 추천 엔진
3. 링크 기반 유사주제 생성기
4. 게시 자동화 (멀티플랫폼 확장, 스케줄링)
5. 모니터링/애널리틱스/최적화 루프

**콘텐츠 생성 파이프라인을 가장 먼저 구축하기로 한 이유**: 실제로 게시 가능한 영상이 없으면 이 사업의 가장 큰 리스크 요소들(YouTube 파트너 프로그램 승인, AI 콘텐츠 정책 위반 여부, 실제 시청자 반응)을 검증할 수 없다. 트렌드 추천 엔진은 파이프라인이 소비할 "주제"가 있어야 의미가 있으므로, 먼저 하나의 검증된 주제로 파이프라인을 안정화한 뒤 주제 추천을 자동화하는 순서가 리스크가 낮다.

## 3. 콘텐츠 니치 선정 근거 (리서치 결과)

### 3.1 검토한 3가지 포맷과 수익성 비교

| | 이미지 슬라이드+내레이션 | AI 아바타(HeyGen 등) | 스토리+게임플레이 배경 |
|---|---|---|---|
| Shorts 광고 RPM | $0.01~0.06/1000회 | Shorts 자체는 비슷하게 낮음 (인용된 고수치는 스폰서/제휴 등 혼합 수익으로 추정) | $2~5는 대부분 **롱폼** 데이터 기준. Shorts는 포맷 무관하게 낮음 |
| 정책 리스크 | **높음** — 템플릿화된 AI 슬라이드는 "inauthentic content" 정책 대상 | 낮음 — 일관된 페르소나가 "저작자성" 인정에 유리 | 낮음 — 실제 편집/연기 관점이 있으면 안전 |
| 실사례 | 2026년 1월 채널 16개(구독자 3,500만, 조회수 47억, 연 추정 $1000만) 대량생산 콘텐츠로 **삭제** | 소규모 성공 사례 다수, 대박은 드묾 | "Am I The Jerk?" 채널 — 구독자 110만, 월 $20K (2021년부터 4년+ 누적) |

핵심 인사이트: Shorts 광고 수익 자체는 포맷과 무관하게 매우 낮다 (월 1000만~5000만 조회수로도 $200~2,000 수준). "빠른 수익화"의 실제 병목은 포맷 선택이 아니라 (a) YPP 자격(구독자 1,000명 + Shorts 조회수 1,000만/90일)에 정지 없이 도달하는 것, (b) 광고 수익만으로는 부족하므로 제휴/스폰서/롱폼 유입 등으로 다각화하는 것이다. 이 다각화는 v1 이후 과제로 남긴다.

### 3.2 선정된 니치: "특별한 장소에 집짓기" AI 영상

리서치 결과, Kling 2.1/2.5, Hailuo 2.3, Pixverse 5.0, VEO3, Seedance 1.0 Pro 등으로 벙커/컨테이너집/수중가옥 등을 짓는 "AI build timelapse" 장르가 이미 수억 조회수를 내는 검증된 바이럴 카테고리임을 확인했다 (관련 튜토리얼과 팩트체크 기사가 존재할 정도로 하나의 장르로 자리잡음). 사용자가 제안한 "스쿨버스/아마존 창고 등 특별한 장소에 집짓기" 아이디어는 이 장르의 변형이며, 다음 이유로 v1 니치로 채택한다.

- 장소만 바꿔도 무한 변형 가능 — 원래 구상했던 "링크 보고 비슷한 주제 생성" 방식과 구조적으로 일치
- 실제 영상 생성물이므로 이미지 슬라이드보다 "authentic" 콘텐츠로 인정받기 유리 (정책 리스크 낮음)
- 시각적 "만족감(satisfying)"으로 리텐션이 좋음
- 서사(내레이션) 없이도 성립 가능 — 파이프라인 단순화 여지가 있음

**주의점**: 이미 경쟁이 있는 장르이므로 단순 장소 치환만으로는 "템플릿 콘텐츠"로 분류될 위험이 있다 → 4절의 5축 변형 시스템으로 대응한다.

### 3.3 2026년 YouTube 정책 리스크 (설계에 반영된 핵심 제약)

- YouTube는 2026년 "inauthentic content" 정책(구 "repetitious content")을 강화했다. **AI 사용 자체는 위반이 아니며, 대량생산·템플릿화·복제 가능한 저노력 콘텐츠("AI slop")가 위반 대상이다.**
- 2026년 1월, 대량생산 템플릿 콘텐츠를 이유로 채널 16개(구독자 3,500만, 조회수 47억, 연 추정 매출 $1,000만)가 **삭제**(단순 수익정지가 아님)되었다.
- AI 어시스트 콘텐츠도 원본적 관점/독창적 편집이 있으면 완전히 수익화 가능하다.
- YouTube Studio/API에는 "Altered or synthetic content" 자체 신고 토글이 있다. 사실적인 AI 생성/합성 콘텐츠(사람·장소·사건을 오인시킬 수 있는 경우)는 이를 활성화해야 하며, 미신고 시 YouTube가 임의로 라벨을 붙이거나(제거 불가) 광고 수익을 박탈할 수 있다. "특정 장소에 실제로 불가능한 건축물을 짓는" 콘텐츠는 이 조건에 해당하므로 **항상 라벨을 활성화**한다.

## 4. 콘텐츠 포맷 및 5축 변형 시스템

### 4.1 포맷
- 30초 이상 (스토리 비트가 최소 4단계 이상 확보되도록 하여 콘텐츠가 부실해지지 않게 함: 문제 제시 → 진행 → 반전 → 완성)
- 세로형 1080×1920
- v1: 음성 내레이션 없음. 화면 텍스트 자막 + 트렌딩 음악만 사용 (TTS는 제작 단계/비용이 늘어나므로 v1에서는 보류)
- 자막에는 일관된 "브랜드 보이스"(위트있는 코멘터리)를 부여해 단순 정보 나열이 아닌 관점을 부여
- 영어권/글로벌 타겟 (RPM이 한국어권보다 유의미하게 높고, 자막 기반이라 언어 의존도가 낮아 글로벌 타겟팅이 자연스러움)
- **v2 로드맵(범위 밖)**: 중간중간 설명하는 AI 건축업자 캐릭터(내레이션 포함) 추가 — 사용자가 제안했으나 v1은 비용 문제로 텍스트 자막만 사용하고, 파이프라인 안정화 후 재검토

### 4.2 5축 변형 시스템 (정책 리스크 완화 + 흥미도 증대의 핵심 장치)

매 영상 생성 시, 아이디어 생성기(LLM)가 아래 5개 축을 **매번 자유롭게 조합/브레인스토밍**한다. 고정된 리스트에서 슬롯을 치환하는 방식이 아니라, LLM이 과거 조합 이력을 참고해 "이번엔 다른 각도로"라는 지시와 함께 새로 생성한다.

1. **장소**: 예) 스쿨버스, 아마존 창고, 화산 내부, 얼음동굴, 지하철 터널
2. **건축 컨셉/장르**: 예) 럭셔리, 포스트아포칼립스, 미니멀, 스팀펑크, 코티지코어
3. **스토리 훅/반전**: 예) 숨겨진 방 발견, 24시간 챌린지, 이웃 몰래 짓기, 예산 초과 반전
4. **비주얼 스타일**: 예) 포토리얼리스틱, 미니어처 모형풍, 블루프린트 오버레이
5. **음악/오디오 무드**

**중복 회피**: 과거 사용된 조합은 상태 저장소(JSON, 저장소에 커밋)에 기록하고, 아이디어 생성기 프롬프트에 최근 N개 조합을 포함시켜 반복을 피한다.

**추가 다양화 장치**: 샷 구성 순서(오프닝/트랜지션 배치)도 가끔 변주하여 "매번 같은 틀"이라는 인상을 최소화한다.

## 5. 파이프라인 아키텍처

매일 1회, GitHub Actions 스케줄 워크플로우로 실행된다.

```
① 아이디어/변형 생성기 (5축 조합 + 중복회피, LLM)
② 스크립트/스토리보드 생성기
   - 실제 영상생성이 필요한 구간(트랜스포메이션: 짓기 전→중간→완성, 6컷×5초 ≈ 30초)과
     정지이미지 팬줌(Ken Burns) 구간(인트로/디테일/마무리샷)을 구분해 총 30초 이상 확보
   - 스토리 비트 최소 4단계(문제 제시→진행→반전→완성) 보장
   - 화면 자막 텍스트 생성 (브랜드 보이스 반영)
③ 에셋 생성
   - 키프레임 이미지: Nano Banana Pro (~$0.10~0.24/장, 8~12장 — 영상 세그먼트용 + 정지 팬줌용)
   - 영상 세그먼트: 저가 모델(Hailuo 계열, ~$0.01~0.03/초) first-last-frame 보간 방식
   - 음악: YouTube 오디오 라이브러리 (무료, 저작권 리스크 없음)
   - **목표 원가: 영상당 $3~5**
④ 조립/렌더: ffmpeg로 영상 세그먼트 + 정지이미지 팬줌 + 자막 번인 + 음악을 합성해 최종본 생성
⑤ 사람 승인 게이트: 텔레그램 봇으로 완성본 미리보기 + 메타데이터 전송 → 모바일에서 1탭 승인/거부.
   미승인 시 게시하지 않고 폐기 (제작 비용은 이미 소진되지만 게시 리스크는 차단됨)
⑥ 게시: YouTube Data API로 업로드.
   - "Altered or synthetic content" 라벨 자동 활성화 (3.3절 근거)
   - SEO 제목/설명/태그는 ①②에서 생성된 조합 정보 기반으로 자동 생성
⑦ 상태 저장: 사용된 5축 조합, 영상별 실제 비용, 게시된 videoId를 JSON으로 기록해 저장소에 커밋.
   다음 실행의 중복 회피 + 향후 애널리틱스 서브프로젝트의 기반 데이터로 사용
```

## 6. 실행/인프라 환경

- **GitHub Actions 스케줄 워크플로우**를 VM 대신 사용한다. 이유: 상시 서버 관리/패치가 불필요하고, 하루 1회 실행은 무료 티어로 충분하며, ffmpeg 등은 워크플로우 내에서 설치 가능하고, 상태는 저장소 커밋으로 자연히 영속화된다. "운영자 개입 최소화" 목표에 가장 부합하는 선택이다.
- API 키/자격증명은 **GitHub Actions Secrets**에 저장하며, 저장소에 평문으로 커밋하지 않는다.
- **PC 2대 사용 환경 대응**: 이 저장소(https://github.com/MS-Won/Shorts, private) 자체가 프로젝트의 공유 컨텍스트/상태 저장소 역할을 한다. Claude의 세션별 내부 메모리는 머신 로컬이라 두 PC 간 자동 동기화되지 않으므로, 설계·의사결정은 이 스펙 문서처럼 저장소에 커밋된 문서로 관리해 어느 PC에서 작업하든 동일한 컨텍스트를 참조할 수 있게 한다.

## 7. 플랫폼/채널

- v1은 **YouTube Shorts만** 대상으로 하며, 신규 채널을 생성한다.
- TikTok/Instagram Reels 등 멀티플랫폼 확장은 v1 파이프라인이 안정화된 이후 별도 서브프로젝트(4절의 "게시 자동화")에서 다룬다.

## 8. 스코프 아웃 (다음 서브프로젝트에서 다룸)

- 트렌드 분석 기반 주제 추천 엔진
- 링크 기반 유사주제 생성기
- 멀티플랫폼 게시 확장 (TikTok, Reels)
- 성과 분석/최적화 루프 (조회수·수익 데이터를 아이디어 생성기에 피드백)
- AI 내레이터/건축업자 캐릭터 (v2, TTS 포함)

## 9. 참고 자료 (리서치 소스)

- [Faceless YouTube Channel Earnings (2026)](https://www.unkoa.com/faceless-youtube-10000-month-2025/)
- [How Much Do Faceless YouTube Channels Actually Make in 2026?](https://easyviral.ai/blog/how-much-do-faceless-youtube-channels-make-2026)
- [YouTube Monetization 2026: Thresholds and Shorts Changes](https://quasa.io/media/youtube-monetization-2026-new-thresholds-and-shorts-revenue-shifts)
- [Monetize YouTube Shorts with AI Video | HeyGen](https://www.heygen.com/blog/monetizing-youtube-shorts-ai-video-generators)
- [YouTube Shorts RPM in 2026: How Much Creators Really Earn - Mediacube](https://mediacube.io/en-US/blog/youtube-shorts-rpm)
- [$20,000/Month Reading Reddit Posts Aloud](https://www.goodreads.com/author_blog_posts/24490084-20-000-month-reading-reddit-posts-aloud?tab=book)
- [Prebunk: Digging Into AI Videos Of Secret Bunker Construction](https://tech.yahoo.com/ai/articles/prebunk-digging-ai-videos-secret-050905572.html)
- [How I Make Viral AI Bunker Shorts With $0 (Full Tutorial)](https://www.youtube.com/watch?v=KwGXOkkKkTs)
- [Why YouTube suspended thousands of AI channels - and how to protect yours – MilX](https://milx.app/en/news/why-youtube-just-suspended-thousands-of-ai-channels-and-how-to-protect-yours)
- [Will AI Content Get You Demonetized on YouTube? The 2026 Inauthentic-Content Policy](https://lenspov.com/articles/youtube-ai-content-demonetization-2026)
- [AI Video Model Pricing (Aug 2026): Official Per-Second Rates](https://invideo.io/blog/ai-video-model-pricing/)
- [Cheapest AI Video Generation APIs in 2026: Price Comparison](https://www.atlascloud.ai/blog/guides/cheapest-ai-video-generation-api-2026)
- [Nano Banana Pro API Pricing](https://www.pixazo.ai/blog/nano-banana-pro-cheapest-pricing)
- [YouTube Altered or Synthetic Content Disclosure Policy: Official 2026 Guide](https://minimatters.com/youtube-altered-or-synthetic-content-disclosure/)

## 10. 다음 단계

이 스펙 문서 승인 및 커밋 후, **writing-plans 스킬**을 통해 실제 구현 계획(파이프라인 Python 코드 구조, GitHub Actions 워크플로우 정의, ffmpeg 조립 로직, 텔레그램 봇 연동, YouTube API 업로드 로직 등)을 별도로 수립한다.
