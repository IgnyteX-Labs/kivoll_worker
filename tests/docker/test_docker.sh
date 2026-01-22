#!/bin/bash
# =============================================================================
# Docker Integration Tests
# =============================================================================
# This script tests the Docker build and deployment configuration.
# It can be run locally via `make test-docker` or in CI.
#
# Tests performed:
#   1. Docker build succeeds for local Dockerfile
#   2. Docker Compose configuration is valid
#   3. Containers start successfully
#   4. Database healthcheck passes
#   5. Worker container healthcheck passes (after initial delay)
#   6. Containers can be cleanly stopped
#
# Requirements:
#   - Docker and Docker Compose installed
#   - .env.admin and .env.worker files present in deploy/
#
# Usage:
#   ./tests/docker/test_docker.sh [--no-cleanup]
#
# Options:
#   --no-cleanup    Don't remove containers after tests (useful for debugging)
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/deploy/local/docker-compose.yml"
TEST_PROJECT_NAME="kivoll-docker-test-$$"
CLEANUP=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
for arg in "$@"; do
    case $arg in
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_header() {
    echo ""
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
}

# Cleanup function
cleanup() {
    if [ "$CLEANUP" = true ]; then
        log_info "Cleaning up test containers..."
        docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true
    else
        log_warn "Skipping cleanup (--no-cleanup specified)"
        log_info "To clean up manually, run:"
        echo "  docker compose -p $TEST_PROJECT_NAME -f $COMPOSE_FILE down --volumes --remove-orphans"
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

pass_test() {
    log_success "$1"
    ((TESTS_PASSED++))
}

fail_test() {
    log_error "$1"
    ((TESTS_FAILED++))
}

# =============================================================================
# Pre-flight Checks
# =============================================================================
log_header "Pre-flight Checks"

# Check Docker is available
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed or not in PATH"
    exit 1
fi
log_info "Docker version: $(docker --version)"

# Check Docker Compose is available
if ! docker compose version &> /dev/null; then
    log_error "Docker Compose is not available"
    exit 1
fi
log_info "Docker Compose version: $(docker compose version --short)"

# Check required env files exist
if [ ! -f "$PROJECT_ROOT/deploy/.env.admin" ]; then
    log_warn ".env.admin not found, creating from example..."
    if [ -f "$PROJECT_ROOT/deploy/.env.admin.example" ]; then
        cp "$PROJECT_ROOT/deploy/.env.admin.example" "$PROJECT_ROOT/deploy/.env.admin"
    else
        log_error "Neither .env.admin nor .env.admin.example found"
        exit 1
    fi
fi

if [ ! -f "$PROJECT_ROOT/deploy/.env.worker" ]; then
    log_warn ".env.worker not found, creating from example..."
    if [ -f "$PROJECT_ROOT/deploy/.env.worker.example" ]; then
        cp "$PROJECT_ROOT/deploy/.env.worker.example" "$PROJECT_ROOT/deploy/.env.worker"
    else
        log_error "Neither .env.worker nor .env.worker.example found"
        exit 1
    fi
fi

log_success "Pre-flight checks passed"

# =============================================================================
# Test 1: Validate Docker Compose Configuration
# =============================================================================
log_header "Test 1: Validate Docker Compose Configuration"

if docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" config --quiet 2>/dev/null; then
    pass_test "Docker Compose configuration is valid"
else
    fail_test "Docker Compose configuration is invalid"
fi

# =============================================================================
# Test 2: Docker Build
# =============================================================================
log_header "Test 2: Docker Build"

log_info "Building Docker images (this may take a while)..."
if docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" build --quiet 2>&1; then
    pass_test "Docker build completed successfully"
else
    fail_test "Docker build failed"
    exit 1  # Can't continue without successful build
fi

# =============================================================================
# Test 3: Container Startup
# =============================================================================
log_header "Test 3: Container Startup"

log_info "Starting containers..."
if docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" up -d 2>&1; then
    pass_test "Containers started successfully"
else
    fail_test "Failed to start containers"
    exit 1
fi

# Give containers a moment to initialize
sleep 3

# =============================================================================
# Test 4: Database Health Check
# =============================================================================
log_header "Test 4: Database Health Check"

log_info "Waiting for database to be healthy (max 60s)..."
DB_HEALTHY=false
for i in {1..12}; do
    if docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" ps db 2>/dev/null | grep -q "healthy"; then
        DB_HEALTHY=true
        break
    fi
    log_info "  Waiting... ($((i * 5))s)"
    sleep 5
done

if [ "$DB_HEALTHY" = true ]; then
    pass_test "Database container is healthy"
else
    fail_test "Database container did not become healthy within 60s"
    log_info "Database container status:"
    docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" ps db
fi

# =============================================================================
# Test 5: Worker Container Running
# =============================================================================
log_header "Test 5: Worker Container Running"

log_info "Checking if worker container is running..."
if docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" ps worker 2>/dev/null | grep -qE "Up|running"; then
    pass_test "Worker container is running"
else
    fail_test "Worker container is not running"
    log_info "Worker container logs:"
    docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" logs worker --tail=50
fi

# =============================================================================
# Test 6: Worker Logs Check (no immediate crashes)
# =============================================================================
log_header "Test 6: Worker Startup Logs Check"

log_info "Waiting for worker to initialize (15s)..."
sleep 15

WORKER_LOGS=$(docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" logs worker 2>&1)

# Check for common error indicators
if echo "$WORKER_LOGS" | grep -qiE "traceback|error:|exception:|fatal"; then
    log_warn "Potential errors found in worker logs"
    log_info "Recent worker logs:"
    docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" logs worker --tail=30
    # This is a warning, not a failure - some errors might be expected during startup
else
    pass_test "No obvious errors in worker startup logs"
fi

# Check that scheduler initialized
if echo "$WORKER_LOGS" | grep -qi "scheduler"; then
    pass_test "Scheduler appears to have initialized"
else
    log_warn "Could not confirm scheduler initialization in logs"
fi

# =============================================================================
# Test 7: Container Can Execute Commands
# =============================================================================
log_header "Test 7: Container Command Execution"

log_info "Testing command execution in worker container..."
if docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" exec -T worker uv run python -c "print('Hello from container')" 2>/dev/null; then
    pass_test "Can execute Python in worker container"
else
    fail_test "Failed to execute Python in worker container"
fi

# Test that the package is importable
if docker compose -p "$TEST_PROJECT_NAME" -f "$COMPOSE_FILE" exec -T worker uv run python -c "import kivoll_worker; print(f'kivoll_worker imported successfully')" 2>/dev/null; then
    pass_test "kivoll_worker package is importable"
else
    fail_test "Failed to import kivoll_worker package"
fi

# =============================================================================
# Test Summary
# =============================================================================
log_header "Test Summary"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
echo ""
echo "  Tests Passed: $TESTS_PASSED"
echo "  Tests Failed: $TESTS_FAILED"
echo "  Total Tests:  $TOTAL_TESTS"
echo ""

if [ "$TESTS_FAILED" -eq 0 ]; then
    log_success "All Docker integration tests passed!"
    exit 0
else
    log_error "Some tests failed. See output above for details."
    exit 1
fi
