#!/usr/bin/env bash
# Path: start.sh
set -e

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }

echo ""
echo -e "${BLUE}🚀  Starting TradeAI Platform...${NC}"
echo ""

# ── Auto-detect docker compose syntax ────────────────────────
run_compose() {
  # Try new plugin syntax first, fall back to standalone
  if docker-compose version &>/dev/null 2>&1; then
    docker-compose "$@"
  else
    warn "docker-compose not found — skipping container start"
    warn "Make sure PostgreSQL (port 5432) and Redis (port 6379) are already running"
    return 1
  fi
}

# ── Start DB containers ────────────────────────────────────────
info "Starting PostgreSQL and Redis..."
if run_compose up postgres redis -d 2>/dev/null; then
  info "Waiting for databases..."
  sleep 5
  success "Databases running"
fi

# ── Start backend ─────────────────────────────────────────────
info "Starting FastAPI backend on http://localhost:8000 ..."
cd backend
if [ -d "venv" ]; then
  source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
  > /tmp/tradeai-backend.log 2>&1 &
echo $! > /tmp/tradeai-backend.pid
success "Backend started (PID: $(cat /tmp/tradeai-backend.pid))"
cd ..

# ── Wait for backend ──────────────────────────────────────────
info "Waiting for backend to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    success "Backend is ready!"
    break
  fi
  sleep 1
  [ "$i" -eq 30 ] && warn "Backend slow to start — check: tail -f /tmp/tradeai-backend.log"
done

# ── Start frontend ────────────────────────────────────────────
info "Starting Next.js frontend on http://localhost:3001 ..."
cd frontend
npm run dev > /tmp/tradeai-frontend.log 2>&1 &
echo $! > /tmp/tradeai-frontend.pid
success "Frontend started (PID: $(cat /tmp/tradeai-frontend.pid))"
cd ..

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   🎉  TradeAI Platform is running!                              ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║   🌐  Frontend:   http://localhost:3001                          ║${NC}"
echo -e "${GREEN}║   🔧  API:        http://localhost:8000                          ║${NC}"
echo -e "${GREEN}║   📚  API Docs:   http://localhost:8000/api/docs                 ║${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║   👤  Login:      demo@tradeai.com  /  Demo1234!                ║${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║   📋  Logs:                                                      ║${NC}"
echo -e "${GREEN}║       tail -f /tmp/tradeai-backend.log                          ║${NC}"
echo -e "${GREEN}║       tail -f /tmp/tradeai-frontend.log                         ║${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║   🛑  Stop: bash stop.sh                                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

tail -f /tmp/tradeai-backend.log
