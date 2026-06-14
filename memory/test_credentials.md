# Test Credentials

## Demo User (TradeAI)
- **Email**: demo@tradeai.com
- **Password**: Demo1234!
- **Endpoint**: POST /api/v1/auth/login

## Database
- **PostgreSQL**: postgresql://trader:trader123@localhost:5432/tradeai
- **Redis**: redis://localhost:6379

## URLs
- **Frontend**: https://fc7e60fe-65a9-4620-9382-a46d2d9394ee.preview.emergentagent.com/
- **Backend Base URL**: https://fc7e60fe-65a9-4620-9382-a46d2d9394ee.preview.emergentagent.com (routes /api/* to FastAPI on port 8001)
- **API prefix**: /api/v1
- **API docs**: /api/docs

## LLM
- Backend uses `EMERGENT_LLM_KEY` (Anthropic Claude Sonnet 4.6 for strategy generation, Haiku 4.5 for sentiment)
