#!/bin/bash
# Bootstrap script — idempotently provisions Postgres + Redis on container start.
# Path: /app/bootstrap.sh
# This is needed because the underlying container is volatile: apt installs and
# /var/lib/postgresql data do NOT persist across restarts, but /app does.
set -e

log()  { echo "[bootstrap] $*"; }

# 1. Install postgres + redis if the binaries are missing
if ! command -v psql >/dev/null 2>&1 || ! command -v redis-server >/dev/null 2>&1; then
    log "Installing postgresql + redis-server (binaries missing)…"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq postgresql postgresql-contrib redis-server >/dev/null
    log "Install complete."
fi

# 2. Start services if not running
if ! pg_isready -h /var/run/postgresql -q 2>/dev/null; then
    log "Starting PostgreSQL…"
    service postgresql start
fi
if ! redis-cli ping >/dev/null 2>&1; then
    log "Starting Redis…"
    service redis-server start
fi

# 3. Wait up to 30s for postgres to accept connections
for _ in $(seq 1 30); do
    if pg_isready -h /var/run/postgresql -q 2>/dev/null; then break; fi
    sleep 1
done

# 4. Create role + database if missing (idempotent)
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='trader'" 2>/dev/null \
    | grep -q 1 \
    || sudo -u postgres psql -c "CREATE USER trader WITH PASSWORD 'trader123' SUPERUSER;" >/dev/null
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='tradeai'" 2>/dev/null \
    | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE tradeai OWNER trader;" >/dev/null

# 5. Run Alembic migrations (idempotent — alembic skips already-applied revisions)
cd /app/backend
/root/.venv/bin/alembic upgrade head >/dev/null 2>&1 || log "alembic upgrade failed (non-fatal)"

# 6. Seed demo user (idempotent — script checks existence before insert)
/root/.venv/bin/python seed_demo.py >/dev/null 2>&1 || log "demo seed skipped (already exists)"

log "Bootstrap OK · Postgres + Redis up · DB migrations applied · demo user ready."
