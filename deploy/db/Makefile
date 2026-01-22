.PHONY: help up down rebuild reset

# Default target to display help
help:
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║          Development Database Management Commands              ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@echo "  make up       - Start the development database (PostgreSQL)"
	@echo "  make down     - Stop the development database"
	@echo "  make rebuild  - Rebuild the database from docker-compose.yml"
	@echo "  make reset    - Reset the database (down + up)"
	@echo "  make help     - Display this help message"
	@echo ""
	@echo "────────────────────────────────────────────────────────────────"
	@echo ""

# Start the database
up:
	@echo "Starting development database..."
	docker-compose up -d
	@echo "✓ Database is starting. Waiting for health check..."
	@docker-compose ps

# Stop the database
down:
	@echo "Stopping development database..."
	docker-compose down
	@echo "✓ Database stopped"

# Rebuild the database
rebuild: down
	@echo "Rebuilding development database..."
	docker-compose up -d
	@echo "✓ Database rebuilt and started"
	@docker-compose ps

# Reset the database (stop, delete volume, and start)
reset: down
	@echo "Deleting database volume..."
	docker-compose down -v
	@echo "Reinitializing database..."
	docker-compose up -d
	@echo "✓ Database reset complete"
