.PHONY: install test test-cov lint format typecheck docs build clean check help docker-build docker-headless docker-shell env up-test-db down-test-db test-postgres test-docker db-up db-down db-rebuild db-reset docker-sync

# Docker image name
DOCKER_IMAGE ?= kivoll_worker:latest
DOCKER_CONTAINER ?= kivoll_worker

# Default target
check: lint format typecheck test-cov test test-postgres

help:
	@echo "Running the application:"
	@echo "  install        	Install dependencies"
	@echo "  env            	Open shell with .env environment loaded"
	@echo "  build          	Build the package"
	@echo "  clean          	Remove build artifacts"
	@echo "  check          	Run lint, formatting, typecheck, and test (default)"
	@echo ""
	@echo "Code quality:"
	@echo "  lint           	Run lint checks"
	@echo "  format         	Run ruff formatting"
	@echo "  typecheck      	Run type checks"
	@echo ""
	@echo "Docker targets:"
	@echo "  docker-build   	Build Docker image from deploy/Dockerfile"
	@echo "  docker-shell   	Open interactive shell in Docker container (most useful for development)"
	@echo "  docker-headless    Run Docker container headless"
	@echo ""
	@echo "Database management:"
	@echo "  db-up          	Start the development database (PostgreSQL)"
	@echo "  db-down        	Stop the development database"
	@echo "  db-rebuild     	Rebuild the database from docker-compose.yml"
	@echo "  db-reset       	Reset the database (down + up)"
	@echo ""
	@echo "Testing:"
	@echo "  test           	Run tests (sqlite-only by default)"
	@echo "  test-cov       	Run tests with coverage report"
	@echo "  test-postgres  	Run Postgres integration tests"
	@echo "  test-docker    	Run Docker build and integration tests"
	@echo "  up-test-db     	Start local Postgres for tests (port 5433)"
	@echo "  down-test-db   	Stop local Postgres for tests"
	@echo ""
	@echo "Documentation:"
	@echo "  docs           	Build documentation"
	@echo "  help           	Show this help message"
	@echo ""
	@echo "Quick start:"
	@echo "  1. make install                            # Install dependencies"
	@echo "  2. cp deploy/.env.example deploy/.env      # Copy env template"
	@echo "  3. Edit deploy/.env with your settings"
	@echo "  4. make env                                # Open shell with env loaded"
	@echo "     OR: make docker-build && make docker-headless # Run in Docker (headless)"

install:
	uv sync --group dev

test:
	uv run pytest
	@echo "pytest complete"

test-cov:
	uv run pytest --cov=kivoll_worker --cov-report=term-missing --cov-report=html:coverage_html
	@echo "Coverage report generated. View at: file://$$(pwd)/coverage_html/index.html"

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
	rm -rf coverage_html/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} +

docker-build:
	@echo "Building Docker image from deploy/Dockerfile..."
	docker build -t $(DOCKER_IMAGE) -f deploy/Dockerfile .

docker-headless:
	@if [ ! -f deploy/.env ]; then \
		echo "Error: deploy/.env file not found!"; \
		echo "Please copy deploy/.env.example to deploy/.env and update it with your settings."; \
		exit 1; \
	fi
	@if [ ! -f deploy/.env.docker ]; then \
		echo "Error: deploy/.env.docker file not found!"; \
		exit 1; \
	fi
	@echo "Starting Docker container with .env configuration..."
	docker run --rm -d \
		--name $(DOCKER_CONTAINER) \
		--network local-kivoll-db_default \
		--env-file deploy/.env \
		--env-file deploy/.env.docker \
		-v $(PWD)/data:/app/data \
		$(DOCKER_IMAGE)

up: docker-headless

docker-shell:
	@if [ ! -f deploy/.env ]; then \
		echo "Error: deploy/.env file not found!"; \
		echo "Please copy deploy/.env.example to deploy/.env and update it with your settings."; \
		exit 1; \
	fi
	@if [ ! -f deploy/.env.docker ]; then \
		echo "Error: deploy/.env.docker file not found!"; \
		exit 1; \
	fi
	@echo "Opening shell in Docker container..."
	docker run --rm -it \
		--name $(DOCKER_CONTAINER)-shell \
		--network local-kivoll-db_default \
		--env-file deploy/.env \
		--env-file deploy/.env.docker \
		-v $(PWD)/src:/app/src \
		--entrypoint /bin/bash \
		$(DOCKER_IMAGE)

env:
	@if [ ! -f deploy/.env ]; then \
		echo "Error: deploy/.env file not found!"; \
		echo "Please copy deploy/.env.example to deploy/.env and update it with your settings."; \
		exit 1; \
	fi
	@echo "To load environment variables, run:"
	@echo "  set -a; . ./deploy/.env; set +a"


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

# Docker integration tests - can be run locally or in CI
# Tests that Docker builds succeed, containers start, and healthcheck passes
test-docker:
	@echo "Running Docker integration tests..."
	./tests/docker/test_docker.sh

# Database management targets
db-up:
	@echo "Starting development database..."
	docker-compose -f deploy/db/docker-compose.yml up -d
	@echo "✓ Database is starting. Waiting for health check..."
	@docker-compose -f deploy/db/docker-compose.yml ps

db-down:
	@echo "Stopping development database..."
	docker-compose -f deploy/db/docker-compose.yml down
	@echo "✓ Database stopped"

db-rebuild: db-down
	@echo "Rebuilding development database..."
	docker-compose -f deploy/db/docker-compose.yml up -d --build
	@echo "✓ Database rebuilt and started"
	@docker-compose -f deploy/db/docker-compose.yml ps

db-reset: db-down
	@echo "Deleting database volume..."
	docker volume rm $$(docker volume ls -q | grep pgdata) 2>/dev/null || true
	docker-compose -f deploy/db/docker-compose.yml down -v
	@echo "✓ Database reset complete"

