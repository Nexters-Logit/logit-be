.PHONY: help install up down restart logs test clean migrate migrate-create dev build

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "📦 Logit Server - Available Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with uv
	uv sync

# Docker Commands
up: ## Start all services (with auto-migration)
	docker compose up -d

dev: ## Start all services in watch mode (auto-reload)
	docker compose up --watch

build: ## Build Docker images
	docker compose build

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

logs: ## View logs (follow mode)
	docker compose logs -f

logs-app: ## View app logs only
	docker compose logs -f app

# Database Commands
migrate: ## Run database migrations (auto via entrypoint.sh)
	docker compose exec app alembic upgrade head

migrate-create: ## Create new migration (example: make migrate-create MSG="Add user table")
	docker compose exec app alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback last migration
	docker compose exec app alembic downgrade -1

migrate-history: ## Show migration history
	docker compose exec app alembic history

# Test Commands
test: ## Run tests
	docker compose exec app pytest

test-cov: ## Run tests with coverage
	docker compose exec app pytest --cov=app --cov-report=html

test-local: ## Run tests locally (requires uv sync)
	uv run pytest

# Database Management
db-shell: ## Open PostgreSQL shell
	docker compose exec postgres psql -U logit -d logit_db

db-reset: ## Reset database (WARNING: deletes all data)
	docker compose down -v
	docker compose up -d postgres
	sleep 5
	docker compose up -d app

# Cleanup Commands
clean: ## Stop containers and remove volumes
	docker compose down -v

clean-all: ## Deep clean (containers, volumes, images)
	docker compose down -v --rmi all
	docker system prune -f

# Development Commands
shell: ## Open shell in app container
	docker compose exec app /bin/bash

format: ## Format code with ruff
	uv run ruff format .

lint: ## Lint code with ruff
	uv run ruff check .

type-check: ## Type check with mypy
	uv run mypy src/

# Quick Start
quick-start: build up ## Build and start all services
	@echo "✅ Services started! Visit http://localhost:8000/docs"
