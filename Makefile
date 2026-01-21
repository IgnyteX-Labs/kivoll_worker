.PHONY: install test lint format typecheck docs build clean check help up relaunch recreate down up-test-db down-test-db test-postgres

# Mode: local (default) or prod
MODE ?= local
COMPOSE_FILE := deploy/$(MODE)/docker-compose.yml

# Default target
check: lint format typecheck test test-postgres

help:
	@echo "Available targets:"
	@echo "  install        Install dependencies"
	@echo "  test           Run tests (sqlite-only by default)"
	@echo "  test-postgres  Run Postgres integration tests via docker compose"
	@echo "  up-test-db     Start local Postgres for tests (port 5433)"
	@echo "  down-test-db   Stop local Postgres for tests"
	@echo "  lint           Run lint checks"
	@echo "  typecheck      Run type checks"
	@echo "  format         Run ruff formatting"
	@echo "  docs           Build documentation"
	@echo "  build          Build the package"
	@echo "  clean          Remove build artifacts"
	@echo "  check          Run lint, formatting, typecheck, and test (default)"
	@echo ""
	@echo "Docker targets (MODE=local or prod, default: local):"
	@echo "  up             Start containers"
	@echo "  relaunch       Rebuild and restart containers (use for local code changes)"
	@echo "  recreate       Full rebuild (--no-cache in prod for new git commits)"
	@echo "  down           Stop and remove containers"
	@echo ""
	@echo "  Note: For local development, use 'relaunch' to pick up code changes."
	@echo "        Use 'recreate' only when dependencies change."
	@echo ""
	@echo "  help           Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make up                 # Start local dev containers"
	@echo "  make MODE=prod up       # Start production containers"
	@echo "  make MODE=prod recreate # Full rebuild for production"

install:
	uv sync --group dev

test:
	uv run pytest
	@echo "pytest complete"

lint:
	uv run ruff check --fix
	@echo "ruff check complete"

format:
	uv run ruff format .
	@echo "ruff format complete"

typecheck:
	uv run mypy src
	@echo "typecheck complete"

docs:
	uv run --group docs make html -C docs
	@echo "Documentation built. View at: file://$$(pwd)/docs/build/html/index.html"

build:
	uv build

clean:
	rm -rf dist/
	rm -rf docs/build/
	rm -rf .mypy_cache/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +

up:
	docker compose -f $(COMPOSE_FILE) up -d

relaunch:
	docker compose -f $(COMPOSE_FILE) up -d --build --force-recreate

recreate:
	docker compose -f $(COMPOSE_FILE) down --volumes --remove-orphans
	docker compose -f $(COMPOSE_FILE) build --pull --no-cache
	docker compose -f $(COMPOSE_FILE) up -d

down:
	docker compose -f $(COMPOSE_FILE) down --volumes --remove-orphans

up-test-db:
	docker compose -f deploy/test/docker-compose.yml up -d --wait

down-test-db:
	docker compose -f deploy/test/docker-compose.yml down -v

# Runs only the Postgres-marked tests (skips automatically if TEST_POSTGRES_URL not set).
# We set TEST_POSTGRES_URL here so the tests are enabled.
# Note: this uses port 5433 on purpose to avoid clashing with any local Postgres.

test-postgres: up-test-db
	TEST_POSTGRES_URL=postgresql+psycopg://postgres:postgres@localhost:5433/postgres \
		uv run pytest -q -k postgres
	$(MAKE) down-test-db
