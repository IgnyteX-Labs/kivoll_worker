.PHONY: install test lint format typecheck docs build clean check help deploy

# Default target
check: lint format typecheck test

help:
	@echo "Available targets:"
	@echo "  install    Install dependencies"
	@echo "  test       Run tests"
	@echo "  lint       Run lint checks"
	@echo "  typecheck  Run type checks"
	@echo "  format     Run ruff formatting"
	@echo "  docs       Build documentation"
	@echo "  build      Build the package"
	@echo "  clean      Remove build artifacts"
	@echo "  check      Run lint, formatting, typecheck, and test (default)"
	@echo "  deploy     Deploy the application using Docker Compose"
	@echo "  help       Show this help message"

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
	docker compose -f deploy/docker-compose.yml up -d
