#!/usr/bin/env bash
echo "🛑 Stopping TradeAI..."
[ -f /tmp/tradeai-backend.pid ]  && kill "$(cat /tmp/tradeai-backend.pid)"  2>/dev/null && rm -f /tmp/tradeai-backend.pid  && echo "✅ Backend stopped"
[ -f /tmp/tradeai-frontend.pid ] && kill "$(cat /tmp/tradeai-frontend.pid)" 2>/dev/null && rm -f /tmp/tradeai-frontend.pid && echo "✅ Frontend stopped"
fuser -k 8000/tcp 2>/dev/null || lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fuser -k 3001/tcp 2>/dev/null  || lsof -ti:3001 | xargs kill -9 2>/dev/null || true
docker-compose down 2>/dev/null && echo "✅ Docker stopped" || true
echo "✅ Done"
