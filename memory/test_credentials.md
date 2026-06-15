# TradeAI — Test Credentials

## Demo Account
- Email: `demo@tradeai.com`
- Password: `Demo1234!`
- Created via: `/root/.venv/bin/python /app/backend/seed_demo.py` (idempotent)

## Backend
- Local URL: `http://localhost:8001`
- External URL: `https://5e0d847d-b059-4b8e-9818-9c3a87b9ce69.preview.emergentagent.com`
- API prefix: `/api/v1`
- Auth: JWT Bearer token from `POST /api/v1/auth/login` (body: `{"email":..., "password":...}`)
- Health: `GET /health` (no auth)

## Frontend
- Local URL: `http://localhost:3000`
- External URL: `https://5e0d847d-b059-4b8e-9818-9c3a87b9ce69.preview.emergentagent.com`
- Framework: Next.js 14 (App Router)
- Env: `frontend/.env.local` -> `NEXT_PUBLIC_API_URL`

## Postgres (running locally in pod)
- Database: `tradeai`
- User/Pass: `trader` / `trader123`
- Port: `5432`

## Redis (running locally in pod)
- URL: `redis://localhost:6379`

## Notes
- `EMERGENT_LLM_KEY` is left blank in this env — AI features will use rule-based fallback (no AI provider keys provided).
- Brokers (Angel One / Zerodha) are NOT connected — endpoints requiring broker session will return `no_live_data` or empty.

## Live integrations wired (iter8)
- **OpenAI**: `OPENAI_API_KEY` in `backend/.env` — sentiment + strategy fall back to `gpt-4o-mini` direct API when no Emergent key. Current key is valid but quota-exhausted (HTTP 429 `insufficient_quota` — needs billing top-up at https://platform.openai.com/settings/organization/billing).
- **Angel One** (broker): connected as `N513357` via `POST /api/v1/brokers/angel-one/connect`. Session stored in `broker_connections` table. Portfolio / Positions now flow live data (currently 0 holdings for this client).
- **Telegram**: bot token + chat_id saved on demo user via `PUT /api/v1/users/me`. Verified by creating an alert with `channels:["in_app","telegram"]` — alert engine fired and `POST api.telegram.org/.../sendMessage` returned 200 OK.
- **OpenRouter**: already listed as a provider in `/api/v1/ai-models/providers`. To enable, user must hit `POST /api/v1/ai-models` with `{"provider":"openrouter","api_key":"<sk-or-...>","is_active":true}`.
