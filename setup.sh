#!/usr/bin/env bash
# Path: setup.sh — One-shot installer
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   TradeAI Platform — Setup               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Prereqs ───────────────────────────────────────────────────
command -v python3 &>/dev/null || error "Python 3.11+ required"
command -v node    &>/dev/null || error "Node.js 18+ required"
command -v npm     &>/dev/null || error "npm required"
success "Prerequisites OK"

# ── Backend ───────────────────────────────────────────────────
info "Setting up backend..."
cd backend
[ ! -d "venv" ] && python3 -m venv venv && success "venv created"
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
pip install --upgrade pip -q
pip install -r requirements.txt -q
success "Python packages installed"
[ ! -f ".env" ] && cp .env.example .env && warn "Created .env — add your API keys!"
cd ..

# ── Frontend ──────────────────────────────────────────────────
info "Setting up frontend..."
cd frontend
npm install --silent
success "Node packages installed"
if [ ! -f ".env.local" ]; then
  printf "NEXT_PUBLIC_API_URL=http://localhost:8000\nNEXT_PUBLIC_APP_NAME=TradeAI\n" > .env.local
  success "Created .env.local"
fi
cd ..

# ── Databases ─────────────────────────────────────────────────
if command -v docker-compose &>/dev/null; then
  info "Starting PostgreSQL and Redis via docker-compose..."
  docker-compose up postgres redis -d
  sleep 6
  success "Databases ready"

  info "Running database migrations..."
  cd backend
  source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
  alembic upgrade head
  success "Migrations applied"
  cd ..
else
  warn "docker-compose not found — start PostgreSQL + Redis manually then run:"
  warn "  cd backend && source venv/bin/activate && alembic upgrade head"
fi

# ── Demo user ─────────────────────────────────────────────────
info "Creating demo user..."
cd backend
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
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
                print("✅ Demo user created: demo@tradeai.com / Demo1234!")
            else:
                print("ℹ️  Demo user already exists")
    except Exception as e:
        print(f"⚠️  Demo user skipped: {e}")
asyncio.run(main())
PYEOF
cd ..

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅  Setup complete!                                         ║${NC}"
echo -e "${GREEN}║  Login: demo@tradeai.com  /  Demo1234!                      ║${NC}"
echo -e "${GREEN}║  Run:   bash start.sh                                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
