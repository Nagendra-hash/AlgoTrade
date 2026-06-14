# ─── TradeAI Platform Makefile ────────────────────────────────────
# Targets:
#   make run          — Start full dev environment (DBs + backend + frontend)
#   make stop         — Stop all services
#   make logs         — Tail backend logs
#   make db           — Start databases only (PostgreSQL + Redis)
#   make db-migrate   — Run alembic migrations
#   make test         — Run all checks (backend tests + frontend checks)
#   make test-backend — Run backend integration tests
#   make test-frontend— Run frontend type-check + lint
#   make typecheck    — Frontend TypeScript type-check only
#   make lint         — Frontend ESLint only
#   make setup        — Install all dependencies
#   make help         — Show this help
# ─────────────────────────────────────────────────────────────────
.PHONY: run stop logs db db-migrate db-backend-start backend-start frontend-start test test-backend test-frontend typecheck lint setup help

BACKEND_DIR   = backend
FRONTEND_DIR  = frontend
BACKEND_PORT  = 8000
FRONTEND_PORT = 3001
BACKEND_PID   = /tmp/tradeai-backend.pid
FRONTEND_PID  = /tmp/tradeai-frontend.pid
BACKEND_LOG   = /tmp/tradeai-backend.log
FRONTEND_LOG  = /tmp/tradeai-frontend.log

# Colours for output
GREEN  = \033[0;32m
RED    = \033[0;31m
BLUE   = \033[0;34m
YELLOW = \033[1;33m
NC     = \033[0m

# ── Top-level ────────────────────────────────────────────────────

run: db-backend-start frontend-start  ## Start full dev environment
	@printf "\n$(GREEN)╔══════════════════════════════════════════════════════════════════╗$(NC)\n"
	@printf "$(GREEN)║   🎉  TradeAI Platform is running!                              ║$(NC)\n"
	@printf "$(GREEN)╠══════════════════════════════════════════════════════════════════╣$(NC)\n"
	@printf "$(GREEN)║                                                                  ║$(NC)\n"
	@printf "$(GREEN)║   🌐  Frontend:   http://localhost:$(FRONTEND_PORT)                          ║$(NC)\n"
	@printf "$(GREEN)║   🔧  API:        http://localhost:$(BACKEND_PORT)                          ║$(NC)\n"
	@printf "$(GREEN)║   📚  API Docs:   http://localhost:$(BACKEND_PORT)/api/docs                 ║$(NC)\n"
	@printf "$(GREEN)║                                                                  ║$(NC)\n"
	@printf "$(GREEN)║   👤  Login:      demo@tradeai.com  /  Demo1234!                ║$(NC)\n"
	@printf "$(GREEN)║                                                                  ║$(NC)\n"
	@printf "$(GREEN)║   📋  Logs:       make logs                                      ║$(NC)\n"
	@printf "$(GREEN)║   🛑  Stop:       make stop                                      ║$(NC)\n"
	@printf "$(GREEN)╚══════════════════════════════════════════════════════════════════╝$(NC)\n"
	@printf "\n"

stop:  ## Stop all services
	@printf "$(BLUE)[stop]$(NC) Stopping services...\n"
	@if [ -f $(BACKEND_PID) ]; then \
		kill "$$(cat $(BACKEND_PID))" 2>/dev/null && printf "$(GREEN)✅$(NC) Backend stopped\n" || true; \
		rm -f $(BACKEND_PID); \
	fi
	@if [ -f $(FRONTEND_PID) ]; then \
		kill "$$(cat $(FRONTEND_PID))" 2>/dev/null && printf "$(GREEN)✅$(NC) Frontend stopped\n" || true; \
		rm -f $(FRONTEND_PID); \
	fi
	@docker-compose down 2>/dev/null && printf "$(GREEN)✅$(NC) Databases stopped\n" || printf "$(YELLOW)⚠️$(NC) No docker-compose to stop\n"
	@printf "$(GREEN)✅$(NC) Done.\n"

logs:  ## Tail backend logs
	@tail -f $(BACKEND_LOG)

# ── Database ─────────────────────────────────────────────────────

db:  ## Start PostgreSQL & Redis via docker-compose
	@printf "$(BLUE)[db]$(NC) Starting PostgreSQL & Redis...\n"
	@docker-compose up postgres redis -d 2>/dev/null; \
		result=$$?; \
		if [ $$result -ne 0 ]; then \
			printf "$(YELLOW)⚠️$(NC) docker-compose not found — ensure PostgreSQL (5432) and Redis (6379) are running\n"; \
		fi
	@printf "$(BLUE)[db]$(NC) Waiting for databases...\n"
	@sleep 5
	@printf "$(GREEN)✅$(NC) Databases ready.\n"	db-migrate:  ## Run Alembic database migrations
	@printf "$(BLUE)[db]$(NC) Running migrations...\n"
	cd $(BACKEND_DIR) && alembic upgrade head
	@printf "$(GREEN)✅$(NC) Migrations applied.\n"

# ── Backend ──────────────────────────────────────────────────────

db-backend-start: db db-migrate backend-start

backend-start:  ## Start FastAPI backend (background)
	@printf "$(BLUE)[backend]$(NC) Starting on http://localhost:$(BACKEND_PORT) ...\n"
	@cd $(BACKEND_DIR) && nohup uvicorn app.main:app --host 0.0.0.0 --port $(BACKEND_PORT) --reload \
		> $(BACKEND_LOG) 2>&1 &
	@printf '%d' "$$!" > $(BACKEND_PID)
	@printf "$(GREEN)✅$(NC) Backend started (PID: $$(cat $(BACKEND_PID)))\n"
	@printf "$(BLUE)[backend]$(NC) Waiting for readiness...\n"
	@for i in $$(seq 1 30); do \
		if curl -sf http://localhost:$(BACKEND_PORT)/health >/dev/null 2>&1; then \
			printf "$(GREEN)✅$(NC) Backend is ready!\n"; \
			break; \
		fi; \
		printf '.'; \
		sleep 1; \
	done; \
	printf '\n'

# ── Frontend ─────────────────────────────────────────────────────

frontend-start:  ## Start Next.js frontend (background)
	@printf "$(BLUE)[frontend]$(NC) Starting on http://localhost:$(FRONTEND_PORT) ...\n"
	@cd $(FRONTEND_DIR) && nohup npm run dev > $(FRONTEND_LOG) 2>&1 &
	@printf '%d' "$$!" > $(FRONTEND_PID)
	@printf "$(GREEN)✅$(NC) Frontend started (PID: $$(cat $(FRONTEND_PID)))\n"

# ── Test ────────────────────────────────────────────────────────

test: test-backend test-frontend  ## Run all checks
	@printf "\n$(GREEN)✅  All checks passed!$(NC)\n"

test-backend:  ## Run backend integration tests
	@printf "$(BLUE)[backend]$(NC) Running integration tests...\n"
	@cd $(BACKEND_DIR) && \
		if [ -x venv/bin/python3 ]; then \
			venv/bin/python3 -m pytest tests -v --tb=short; \
		else \
			python3 -m pytest tests -v --tb=short; \
		fi
	@printf "$(GREEN)[backend]$(NC) Tests complete.\n"

test-frontend: typecheck lint  ## Run all frontend checks

typecheck:  ## Frontend TypeScript type check
	@printf "$(BLUE)[frontend]$(NC) Type-checking...\n"
	cd $(FRONTEND_DIR) && npx tsc --noEmit
	@printf "$(GREEN)[frontend]$(NC) TypeScript OK.\n"

lint:  ## Frontend ESLint
	@printf "$(BLUE)[frontend]$(NC) Linting...\n"
	cd $(FRONTEND_DIR) && npm run lint
	@printf "$(GREEN)[frontend]$(NC) Lint OK.\n"

# ── Setup ────────────────────────────────────────────────────────

setup:  ## Install all project dependencies
	@printf "$(BLUE)[setup]$(NC) Installing backend dependencies...\n"
	@cd $(BACKEND_DIR) && \
		if [ ! -d venv ]; then \
			printf "  $(BLUE)Creating Python virtual environment...$(NC)\n"; \
			python3 -m venv venv; \
		fi; \
		if [ -x venv/bin/pip3 ]; then \
			venv/bin/pip3 install -q -r requirements.txt; \
			venv/bin/pip3 install -q pytest pytest-asyncio httpx sendgrid; \
		else \
			pip3 install -q -r requirements.txt; \
			pip3 install -q pytest pytest-asyncio httpx; \
		fi
	@printf "$(GREEN)[setup]$(NC) Backend dependencies installed.\n"
	@printf "$(BLUE)[setup]$(NC) Installing frontend dependencies...\n"
	cd $(FRONTEND_DIR) && npm install --silent
	@printf "$(GREEN)[setup]$(NC) All dependencies installed.\n"

# ── Help ─────────────────────────────────────────────────────────

help:  ## Show this help message
	@printf "\n$(BLUE)Usage:$(NC) make <target>\n\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@printf "\n"
