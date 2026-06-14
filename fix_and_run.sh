#!/usr/bin/env bash
# Full setup + start — run from inside the tradeai folder
# Usage:  cd ~/Pictures/tradeai && bash fix_and_run.sh

set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

[ -f "backend/app/main.py" ] || error "Run this from the tradeai folder! (cd ~/Pictures/tradeai)"

PROJECT_DIR=$(pwd)
FRONTEND_PORT=3001
info "Project: $PROJECT_DIR   Frontend port: $FRONTEND_PORT"

# ── 1. Python venv ────────────────────────────────────────────
info "Setting up Python virtual environment..."
cd "$PROJECT_DIR/backend"
[ ! -d "venv" ] && python3 -m venv venv && success "venv created"
source venv/bin/activate
success "venv activated"

# ── 2. Python packages ────────────────────────────────────────
info "Installing Python packages (first run takes ~2 min)..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
success "Python packages ready"

# ── 3. .env file ──────────────────────────────────────────────
[ ! -f ".env" ] && cp .env.example .env && warn "Created .env — add API keys later (optional)"

# ── 4. PostgreSQL + Redis ─────────────────────────────────────
cd "$PROJECT_DIR"
info "Checking databases..."

pg_isready -U trader -d tradeai -h localhost -p 5432 &>/dev/null 2>&1 && PG_OK=true || PG_OK=false
redis-cli ping &>/dev/null 2>&1 && REDIS_OK=true || REDIS_OK=false

if $PG_OK && $REDIS_OK; then
  success "PostgreSQL and Redis already running"
elif command -v docker-compose &>/dev/null; then
  info "Starting via docker-compose..."
  docker-compose up postgres redis -d
  sleep 6
  success "Containers started"
elif command -v docker &>/dev/null; then
  info "Starting via docker run..."
  docker run -d --name tradeai_postgres \
    -e POSTGRES_USER=trader -e POSTGRES_PASSWORD=trader123 -e POSTGRES_DB=tradeai \
    -p 5432:5432 postgres:15-alpine 2>/dev/null || docker start tradeai_postgres 2>/dev/null || true
  docker run -d --name tradeai_redis \
    -p 6379:6379 redis:7-alpine 2>/dev/null || docker start tradeai_redis 2>/dev/null || true
  sleep 5
  success "Containers started"
else
  info "Installing PostgreSQL and Redis via apt..."
  sudo apt-get update -q
  sudo apt-get install -y -q postgresql redis-server
  sudo service postgresql start
  sudo service redis-server start
  sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename='trader'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE USER trader WITH PASSWORD 'trader123';"
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='tradeai'" | grep -q 1 \
    || sudo -u postgres createdb tradeai --owner=trader
  success "PostgreSQL + Redis installed and started"
fi

# ── 5. Migrations ─────────────────────────────────────────────
info "Running database migrations..."
cd "$PROJECT_DIR/backend"
source venv/bin/activate
alembic upgrade head
success "Database schema ready"

# ── 6. Demo user ──────────────────────────────────────────────
info "Creating demo user..."
python3 - << 'PYEOF'
import asyncio
async def main():
    try:
        from app.core.database import AsyncSessionLocal, engine, Base
        from app.models.user import User
        from app.core.security import hash_password
        from sqlalchemy import select
        import uuid
        from datetime import datetime, timezone
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(User).where(User.email == "demo@tradeai.com"))
            if not r.scalar_one_or_none():
                db.add(User(
                    id=uuid.uuid4(), email="demo@tradeai.com",
                    username="demo_trader", full_name="Demo Trader",
                    hashed_password=hash_password("Demo1234!"),
                    is_active=True, is_verified=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ))
                await db.commit()
                print("✅ Demo user created")
            else:
                print("ℹ️  Demo user already exists")
    except Exception as e:
        print(f"⚠️  Skipped demo user: {e}")
asyncio.run(main())
PYEOF

# ── 7. Frontend packages ──────────────────────────────────────
info "Installing frontend packages..."
cd "$PROJECT_DIR/frontend"
npm install --silent
if [ ! -f ".env.local" ]; then
  printf "NEXT_PUBLIC_API_URL=http://localhost:8000\nNEXT_PUBLIC_APP_NAME=TradeAI\n" > .env.local
fi
success "Frontend ready"

# ── 8. Kill anything already on our ports ─────────────────────
fuser -k 8000/tcp 2>/dev/null || lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fuser -k ${FRONTEND_PORT}/tcp 2>/dev/null || lsof -ti:${FRONTEND_PORT} | xargs kill -9 2>/dev/null || true
sleep 1

# ── 9. Start backend ──────────────────────────────────────────
info "Starting backend on port 8000..."
cd "$PROJECT_DIR/backend"
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
  > /tmp/tradeai-backend.log 2>&1 &
echo $! > /tmp/tradeai-backend.pid
cd "$PROJECT_DIR"

info "Waiting for backend..."
for i in $(seq 1 30); do
  curl -sf http://localhost:8000/health >/dev/null 2>&1 && success "Backend ready!" && break
  sleep 1
  [ "$i" -eq 30 ] && warn "Backend slow — check: tail -f /tmp/tradeai-backend.log"
done

# ── 10. Start frontend on port 3001 ───────────────────────────
info "Starting frontend on port $FRONTEND_PORT..."
cd "$PROJECT_DIR/frontend"
nohup npm run dev > /tmp/tradeai-frontend.log 2>&1 &
echo $! > /tmp/tradeai-frontend.pid
cd "$PROJECT_DIR"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   🎉  TradeAI is running!                                        ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║   🌐  App:        http://localhost:3001                          ║${NC}"
echo -e "${GREEN}║   🔧  API:        http://localhost:8000                          ║${NC}"
echo -e "${GREEN}║   📚  API Docs:   http://localhost:8000/api/docs                 ║${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║   👤  Email:      demo@tradeai.com                               ║${NC}"
echo -e "${GREEN}║   🔑  Password:   Demo1234!                                      ║${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║   📋  Logs:                                                      ║${NC}"
echo -e "${GREEN}║       Backend:   tail -f /tmp/tradeai-backend.log               ║${NC}"
echo -e "${GREEN}║       Frontend:  tail -f /tmp/tradeai-frontend.log              ║${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║   🛑  Stop: bash stop.sh                                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Showing backend logs (Ctrl+C exits logs — app keeps running):"
echo "──────────────────────────────────────────────────────────────"
tail -f /tmp/tradeai-backend.log
