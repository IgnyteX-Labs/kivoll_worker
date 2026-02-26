import json
import time
from unittest.mock import MagicMock

from sqlalchemy.exc import SQLAlchemyError

from kivoll_worker.common.health import HealthMonitor, HealthRequestHandler


class MockEngine:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.connect_called = 0

    def connect(self):
        self.connect_called += 1
        if self.should_fail:
            raise SQLAlchemyError("Connection failed")
        return MagicMock(__enter__=MagicMock(), __exit__=MagicMock())


def test_health_monitor_initial_state():
    """A freshly created HealthMonitor reports healthy with no failures and active scheduler."""
    monitor = HealthMonitor()
    status = monitor.get_status()
    assert status["status"] == "healthy"
    assert status["scheduler"] == "active"
    assert status["database"] == "reachable"
    assert status["recent_failures"] == 0


def test_health_monitor_stale_scheduler():
    """HealthMonitor becomes unhealthy when no tick is received within stale_timeout seconds."""
    # Set stale_timeout to 1 second for testing
    monitor = HealthMonitor(stale_timeout=1)
    # Initially healthy
    assert monitor.get_status()["status"] == "healthy"

    # Wait for it to become stale
    time.sleep(1.1)
    status = monitor.get_status()
    assert status["status"] == "unhealthy"
    assert status["scheduler"] == "stale"

    # Update tick and it should be healthy again
    monitor.update_tick()
    assert monitor.get_status()["status"] == "healthy"


def test_health_monitor_db_failure():
    """HealthMonitor reports unhealthy and 'unreachable' when the database connection fails."""
    engine = MockEngine(should_fail=True)
    monitor = HealthMonitor(db_engine=engine)

    status = monitor.get_status()
    assert status["status"] == "unhealthy"
    assert status["database"] == "unreachable"
    assert engine.connect_called == 1


def test_health_monitor_too_many_failures():
    """HealthMonitor becomes unhealthy once the recorded failure count reaches max_failures."""
    # Max 2 failures in 15 mins
    monitor = HealthMonitor(max_failures=2)

    monitor.record_failure()
    assert monitor.get_status()["status"] == "healthy"
    assert monitor.get_status()["recent_failures"] == 1

    monitor.record_failure()
    status = monitor.get_status()
    assert status["status"] == "unhealthy"
    assert status["recent_failures"] == 2


def test_health_monitor_failure_pruning():
    """Failures outside the tracking window are pruned and no longer count toward the limit."""
    # Small window for testing
    monitor = HealthMonitor(failure_window=0)  # Failures expire immediately for test
    monitor.record_failure()

    time.sleep(0.1)
    assert monitor.get_status()["recent_failures"] == 0


class MockWfile:
    def __init__(self):
        self.data = b""

    def write(self, b):
        self.data += b


class MockRequest:
    def makefile(self, *args, **kwargs):
        return MagicMock()


def test_health_request_handler():
    """HealthRequestHandler returns 200/healthy, 503/unhealthy, and 404 for unknown paths."""
    monitor = HealthMonitor()

    # Mocking BaseHTTPRequestHandler is tricky, let's just test do_GET with mocks
    class MockHandler(HealthRequestHandler):
        def __init__(self, monitor, path):
            self.monitor = monitor
            self.path = path
            self.wfile = MockWfile()
            self.headers_sent = False
            self.response_code = None

        def send_response(self, code):
            self.response_code = code

        def send_header(self, keyword, value):
            pass

        def end_headers(self):
            self.headers_sent = True

    # Test /health success
    handler = MockHandler(monitor, "/health")
    handler.do_GET()
    assert handler.response_code == 200
    assert json.loads(handler.wfile.data.decode())["status"] == "healthy"

    # Test /health failure
    monitor.record_failure()
    monitor.record_failure()
    monitor.record_failure()
    monitor.record_failure()
    monitor.record_failure()  # 5 failures
    handler = MockHandler(monitor, "/health")
    handler.do_GET()
    assert handler.response_code == 503
    assert json.loads(handler.wfile.data.decode())["status"] == "unhealthy"

    # Test 404
    handler = MockHandler(monitor, "/other")
    handler.do_GET()
    assert handler.response_code == 404


def test_health_request_handler_log_message(monkeypatch):
    """Successful /health hits are silently suppressed; other responses are forwarded to cli.log."""
    from kivoll_worker.common.health import cli as health_cli

    logged_messages = []

    def mock_log(msg):
        logged_messages.append(msg)

    monkeypatch.setattr(health_cli, "log", mock_log)

    # We don't want to actually initialize HealthRequestHandler because it tries to parse requests
    # Let's just mock it
    class MockHandler:
        def log_message(self, format, *args):
            # Manually call the implementation from the class
            HealthRequestHandler.log_message(self, format, *args)

    handler = MockHandler()

    # Test suppression of successful healthcheck
    handler.log_message('"%s" %s %s', "GET /health HTTP/1.1", "200", "123")
    assert len(logged_messages) == 0

    # Test logging of failed healthcheck
    handler.log_message('"%s" %s %s', "GET /health HTTP/1.1", "503", "123")
    assert len(logged_messages) == 1
    assert "503" in logged_messages[0]

    # Test logging of other endpoints
    handler.log_message('"%s" %s %s', "GET /other HTTP/1.1", "200", "123")
    assert len(logged_messages) == 2
    assert "/other" in logged_messages[1]
