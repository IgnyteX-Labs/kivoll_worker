"""
Health monitoring and HTTP healthcheck server for kivoll_worker.

This module provides a HealthMonitor to track the application's health state,
including database reachability, scheduler liveness, and recent job failures.
It also includes a lightweight HTTP server to expose this state via a /health endpoint.
"""

import http.server
import json
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from cliasi import Cliasi
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Default healthcheck settings
DEFAULT_HEALTH_PORT = 8000
DEFAULT_FAILURE_WINDOW_MINUTES = 15
DEFAULT_MAX_FAILURES = 5
DEFAULT_STALE_TIMEOUT_SECONDS = 90
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30

cli = Cliasi("health")


class HealthMonitor:
    """
    Tracks application health metrics and evaluates overall health status.
    """

    def __init__(
        self,
        db_engine: Engine | None = None,
        failure_window: int = DEFAULT_FAILURE_WINDOW_MINUTES,
        max_failures: int = DEFAULT_MAX_FAILURES,
        stale_timeout: int = DEFAULT_STALE_TIMEOUT_SECONDS,
    ):
        self.db_engine = db_engine
        self.failure_window = failure_window
        self.max_failures = max_failures
        self.stale_timeout = stale_timeout

        self._last_tick = datetime.now(timezone.utc)
        self._failures: deque[datetime] = deque()
        self._lock = threading.Lock()

    def update_tick(self) -> None:
        """Update the last liveness tick timestamp."""
        with self._lock:
            self._last_tick = datetime.now(timezone.utc)

    def record_failure(self) -> None:
        """Record a job failure timestamp."""
        with self._lock:
            self._failures.append(datetime.now(timezone.utc))
            self._prune_failures()

    def _prune_failures(self) -> None:
        """Remove failures older than the tracking window."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self.failure_window)
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

    def check_db(self) -> bool:
        """Check if the database is reachable."""
        if not self.db_engine:
            return True  # If no DB configured, consider it "healthy" for this check
        try:
            with self.db_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            cli.warn(f"Database healthcheck failed: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Evaluate and return the overall health status."""
        # Check DB outside the lock — a slow/failing query must not block other threads.
        db_reachable = self.check_db()

        with self._lock:
            self._prune_failures()
            now = datetime.now(timezone.utc)

            scheduler_stale = (
                now - self._last_tick
            ).total_seconds() > self.stale_timeout
            too_many_failures = len(self._failures) >= self.max_failures

            healthy = not scheduler_stale and not too_many_failures and db_reachable

            return {
                "status": "healthy" if healthy else "unhealthy",
                "scheduler": "stale" if scheduler_stale else "active",
                "database": "reachable" if db_reachable else "unreachable",
                "recent_failures": len(self._failures),
                "max_failures_allowed": self.max_failures,
                "failure_window_minutes": self.failure_window,
                "last_tick": self._last_tick.isoformat(),
            }


class HealthRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for healthcheck requests."""

    def __init__(
        self,
        request: Any,
        client_address: Any,
        server: http.server.HTTPServer,
        monitor: HealthMonitor,
    ):
        self.monitor = monitor
        super().__init__(request, client_address, server)

    def do_GET(self) -> None:
        """Handle GET requests for /health."""
        if self.path == "/health":
            status = self.monitor.get_status()
            response_code = 200 if status["status"] == "healthy" else 503

            self.send_response(response_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Only log messages that aren't successful healthcheck hits."""
        # args: (requestline, code, size) when called from log_request
        if (
            len(args) > 1
            and str(args[1]) in ("200", "304")
            and "/health" in str(args[0])
        ):
            return

        # Use cli to log other messages (errors or hits to other endpoints)
        cli.log(format % args)


def start_health_server(
    monitor: HealthMonitor, port: int = DEFAULT_HEALTH_PORT
) -> threading.Thread:
    """
    Start the healthcheck HTTP server in a background daemon thread.
    """
    import functools

    handler_factory = functools.partial(HealthRequestHandler, monitor=monitor)

    server = http.server.HTTPServer(("127.0.0.1", port), handler_factory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cli.info(f"Healthcheck server started on port {port}")
    return thread
