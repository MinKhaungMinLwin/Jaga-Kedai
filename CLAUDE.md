# Jaga Kedai — notes for Claude Code

AI partner for Singapore heartland provision shops. FastAPI API (`api/`) on Cloud Run, Firestore,
React 19 + Vite PWA (`web/`) on Firebase Hosting, Gemini via `google-genai`. See README.md.

## Commands
- API: `cd api && uv run uvicorn kedai.main:app --port 8080` · tests `uv run pytest` · lint `uv run ruff check . && uv run ruff format .`
- Web: `cd web && npm run dev` (proxies `/api` to :8080) · `npm test` · `npm run build` (runs typecheck)
- Deploy: `PROJECT_ID=<id> deploy/deploy.sh`

## Principles (don't break these)
- **Hard stops:** AI proposes, the shopkeeper approves. Scans need confirmation; orders go draft → approved → received;
  WhatsApp is sent by the user via a wa.me link. Gemini never sets order quantities — they come from `forecast.plan`.
- Every Gemini call uses structured output and has a non-AI fallback; endpoints return 503 (not 500) when AI is down.
- Firestore is only reached by the API's service account (`firestore.rules` denies clients). `MemoryStore` mirrors
  `FirestoreStore` for dev/tests.
- All UI strings live in `web/src/i18n.ts` in four languages (zh, en, ms, ta); add every new key to all four.
  Layout must not overflow at 390px wide in Tamil/Malay.
- The demo shop re-seeds once per Singapore day; tests pin `today_sg` to 2026-10-13.
- Never commit secrets (`.env` is gitignored).
