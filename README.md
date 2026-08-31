# Shorts

AI 쇼츠 자동 생성 시스템 (수익화 목적).

- 설계 문서: [docs/superpowers/specs/2026-08-31-ai-shorts-content-pipeline-design.md](docs/superpowers/specs/2026-08-31-ai-shorts-content-pipeline-design.md)
- 현재 상태: v1 콘텐츠 생성 파이프라인 설계 확정. 구현 계획 수립 예정.

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
