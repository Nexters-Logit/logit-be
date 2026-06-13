.PHONY: help install up down restart logs test clean migrate migrate-create dev build

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "📦 Logit Server - Available Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with uv
	uv sync

# ─── Local (docker-compose.yml) ──────────────────────────────────────────────

up: ## Start all services (local)
	docker compose up -d

dev: ## Start all services in watch mode (local, auto-reload)
	docker compose up --watch

build: ## Build Docker images (local)
	docker compose build

down: ## Stop all services (local)
	docker compose down

restart: ## Restart all services (local)
	docker compose restart

logs: ## View logs (local, follow mode)
	docker compose logs -f

logs-app: ## View app logs (local)
	docker compose logs -f app

# ─── Dev Server (docker-compose.dev.yml + .env.dev) ──────────────────────────

dev-up: ## Start all services (dev server)
	docker compose -f docker-compose.dev.yml --env-file .env.dev up -d

dev-down: ## Stop all services (dev server)
	docker compose -f docker-compose.dev.yml --env-file .env.dev down

dev-build: ## Build Docker images (dev server)
	docker compose -f docker-compose.dev.yml --env-file .env.dev build

dev-logs: ## View logs (dev server, follow mode)
	docker compose -f docker-compose.dev.yml --env-file .env.dev logs -f

# ─── Production (docker-compose.prod.yml + .env.prod) ────────────────────────

prod-init: ## First-time production setup (starts blue)
	chmod +x scripts/deploy.sh
	./scripts/deploy.sh init

prod-deploy: ## Blue-green deploy to production
	./scripts/deploy.sh deploy

prod-rollback: ## Rollback production to previous version
	./scripts/deploy.sh rollback

prod-status: ## Show production deployment status
	./scripts/deploy.sh status

prod-logs: ## View logs (production, follow mode)
	docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f

prod-down: ## Stop all production services
	docker compose -f docker-compose.prod.yml --env-file .env.prod down

# ─── Database ─────────────────────────────────────────────────────────────────

migrate: ## Run database migrations
	docker compose exec app alembic upgrade head

migrate-create: ## Create new migration (example: make migrate-create MSG="Add user table")
	docker compose exec app alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback last migration
	docker compose exec app alembic downgrade -1

migrate-history: ## Show migration history
	docker compose exec app alembic history

# ─── Test & Code Quality ──────────────────────────────────────────────────────

test: ## Run tests (in container)
	docker compose exec app pytest

test-local: ## Run tests locally (requires uv sync)
	uv run pytest

format: ## Format code with ruff
	uv run ruff format .

lint: ## Lint code with ruff
	uv run ruff check .

type-check: ## Type check with mypy
	uv run mypy src/

# ─── Utils ────────────────────────────────────────────────────────────────────

shell: ## Open shell in app container (local)
	docker compose exec app /bin/bash

db-shell: ## Open PostgreSQL shell (local)
	docker compose exec postgres psql -U logit -d logit_db

clean: ## Stop containers and remove volumes (local)
	docker compose down -v

clean-all: ## Deep clean — containers, volumes, images (local)
	docker compose down -v --rmi all
	docker system prune -f

quick-start: build up ## Build and start all services (local)
	@echo "✅ Services started! Visit http://localhost:8000/docs"
