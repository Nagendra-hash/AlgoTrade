# TradeAI — Test Credentials

## Demo Account
- Email: `demo@tradeai.com`
- Password: `Demo1234!`
- Created via: `python /app/backend/seed_demo.py` (idempotent)

## Backend
- Local URL: `http://localhost:8001`
- External URL: `https://pro-quant-trading.preview.emergentagent.com`
- API prefix: `/api/v1`
- Auth: JWT Bearer token from `POST /api/v1/auth/login`

## Postgres
- Database: `tradeai`
- User: `trader` / `trader123`
- Local port: `5432`

## Redis
- Local: `redis://localhost:6379`

## Emergent Universal LLM Key
- Already configured in `/app/backend/.env` as `EMERGENT_LLM_KEY`
- Powers default fallback for openai / anthropic / gemini providers when user
  has not supplied their own key on the AI Models page.
