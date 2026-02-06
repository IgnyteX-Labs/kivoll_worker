.PHONY: install test lint format typecheck docs build clean
.PHONY: check help docker-build docker-headless docker-shell env
.PHONY: db-up db-down db-reset check-env

# Docker image name
DOCKER_IMAGE ?= kivoll_worker:latest
DOCKER_CONTAINER ?= kivoll_worker

# Database variables
DB_IMAGE = ghcr.io/ignytex-labs/kivoll_db:0.1.0
DEV_CONTAINER = kivoll_dev_db
DEV_VOLUME = pgdata
DEV_PORT = 5432

# Default target
check: lint format typecheck test

help:
	@printf "Running the application:\n"
	@printf "\n"
	@printf "  %-22s %s\n" "install" "Install dependencies"
	@printf "  %-22s %s\n" "env" "Open shell with .env environment loaded"
	@printf "  %-22s %s\n" "build" "Build the package"
	@printf "  %-22s %s\n" "clean" "Remove build artifacts"
	@printf "  %-22s %s\n" "check" "Run lint, formatting, typecheck, and test (default)"
	@printf "  %-22s %s\n" "test" "Test codebase (use m=\"not integration\")"
	@printf "\n"
	@printf "Code quality:\n"
	@printf "  %-22s %s\n" "lint" "Run lint checks"
	@printf "  %-22s %s\n" "format" "Run ruff formatting"
	@printf "  %-22s %s\n" "typecheck" "Run type checks"
	@printf "\n"
	@printf "Docker targets:\n"
	@printf "  %-22s %s\n" "docker-build" "Build Docker image from local.Dockerfile"
	@printf "  %-22s %s\n" "docker-shell" "Open interactive shell in Docker container"
	@printf "  %-22s %s\n" "docker-headless" "Run Docker container headless"
	@printf "\n"
	@printf "Database management:\n"
	@printf "  %-22s %s\n" "db-up" "Start the development database (PostgreSQL)"
	@printf "  %-22s %s\n" "db-down" "Stop the development database"
	@printf "  %-22s %s\n" "db-reset" "Reset the database (down, remove volume, up)"
	@printf "\n"
	@printf "Documentation:\n"
	@printf "  %-22s %s\n" "docs" "Build documentation"
	@printf "  %-22s %s\n" "help" "Show this help message"
	@printf "\n"
	@printf "Quick start:\n"
	@printf "  1. make install\n"
	@printf "  2. cp .env.example .env\n"
	@printf "  3. Edit .env with your settings\n"
	@printf "  4. Run: set -a; . ./.env; set +a\n"

install:
	uv sync --group dev

# Allow passing pytest marker with `m` or arbitrary pytest args via `PYTEST_ARGS`.
# Examples:
#   make test m="not integration"
#   make test PYTEST_ARGS="-k test_name"
ifdef m
PYTEST_MARK := -m "$(m)"
else
PYTEST_MARK :=
endif
PYTEST_EXTRA ?= $(PYTEST_ARGS) $(PYTEST_MARK)

test:
	uv run pytest $(PYTEST_EXTRA) \
		--cov=kivoll_worker \
		--cov-report=term-missing \
		--cov-fail-under=80 \
		--cov-report=html:coverage_html
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
	@echo "Building Docker image from local.Dockerfile..."
	docker build -t $(DOCKER_IMAGE) -f local.Dockerfile .

# Centralized .env check used by multiple targets
check-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found!"; \
		echo "Run: cp .env.example .env"; \
		echo "Then edit .env with your settings."; \
		exit 1; \
	fi

docker-headless: check-env
	@echo "Starting Docker container with .env configuration..."
	docker run --rm -d \
		--name $(DOCKER_CONTAINER) \
		--network host \
		--env-file .env \
		--env DB_HOST=localhost:5432 \
		-v $(PWD)/data:/app/data \
		$(DOCKER_IMAGE)

up: docker-headless

docker-shell: check-env
	@echo "Opening shell in Docker container..."
	docker run --rm -it \
		--name $(DOCKER_CONTAINER)-shell \
		--network host \
		--env-file .env \
		--env DB_HOST=localhost:5432 \
		-v $(PWD)/src:/app/src \
		--entrypoint /bin/bash \
		$(DOCKER_IMAGE)

env: check-env
	@echo "To load environment variables, run:"
	@echo "  set -a; . ./.env; set +a"

# Database management targets
db-up: check-env
	@echo "Starting development database..."
	docker run -d \
		--name $(DEV_CONTAINER) \
		--env-file .env \
		--volume $(DEV_VOLUME):/var/lib/postgresql \
		--restart unless-stopped \
		--publish $(DEV_PORT):5432 \
		$(DB_IMAGE) \
		postgres -c log_statement=all
	@echo "✓ Database is starting. Waiting for health check..."
	@docker ps --filter name=$(DEV_CONTAINER)

db-down:
	@echo "Stopping development database..."
	docker stop $(DEV_CONTAINER) || true
	docker rm $(DEV_CONTAINER) || true
	@echo "✓ Database stopped"

db-reset:
	$(MAKE) db-down
	docker volume rm $(DEV_VOLUME) || true
	@echo "✓ Database data removed"

