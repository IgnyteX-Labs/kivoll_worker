.PHONY: install test lint format typecheck docs build clean check help deploy test-postgres up-test-db down-test-db rebuild recreate down

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
	@echo "  deploy         Deploy the application using Docker Compose (local mode)"
	@echo "  help           Show this help message"

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

deploy:
	docker compose -f deploy/docker-compose.yml --profile local up -d

rebuild:
	docker compose -f deploy/docker-compose.yml --profile local up -d --build --force-recreate

recreate:
	docker rmi deploy-worker:latest
	docker compose -f deploy/docker-compose.yml build --no-cache

down:
	docker compose -f deploy/docker-compose.yml down --volumes --remove-orphans

up-test-db:
	docker compose -f deploy/docker-compose.test.yml up -d --wait

down-test-db:
	docker compose -f deploy/docker-compose.test.yml down -v

# Runs only the Postgres-marked tests (skips automatically if TEST_POSTGRES_URL not set).
# We set TEST_POSTGRES_URL here so the tests are enabled.
# Note: this uses port 5433 on purpose to avoid clashing with any local Postgres.

test-postgres: up-test-db
	TEST_POSTGRES_URL=postgresql+psycopg://postgres:postgres@localhost:5433/postgres \
		uv run pytest -q -k postgres
	$(MAKE) down-test-db
