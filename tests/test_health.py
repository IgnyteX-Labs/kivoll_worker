import json
import time
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from kivoll_worker.common.health import (
    HealthMonitor,
    HealthRequestHandler,
    HealthServer,
    start_health_server,
)


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


def test_health_server_shutdown_calls_server_and_joins_thread():
    """HealthServer.shutdown() calls server.shutdown(), server.server_close(), then thread.join()."""
    from unittest.mock import call

    mock_server = MagicMock()
    mock_thread = MagicMock()
    manager = MagicMock()
    manager.attach_mock(mock_server, "server")
    manager.attach_mock(mock_thread, "thread")

    hs = HealthServer(mock_thread, mock_server)
    hs.shutdown()

    assert manager.mock_calls == [
        call.server.shutdown(),
        call.server.server_close(),
        call.thread.join(),
    ]


def test_start_health_server_custom_port_and_host():
    """start_health_server binds to the given host and port and starts a daemon thread."""
    monitor = HealthMonitor()
    custom_port = 19876
    custom_host = "127.0.0.1"

    with patch("http.server.ThreadingHTTPServer") as mock_http_server_cls:
        mock_server_instance = MagicMock()
        mock_http_server_cls.return_value = mock_server_instance

        result = start_health_server(monitor, port=custom_port, host=custom_host)

    mock_http_server_cls.assert_called_once()
    bind_address = mock_http_server_cls.call_args[0][0]
    assert bind_address == (custom_host, custom_port)
    assert isinstance(result, HealthServer)
    assert result.thread.daemon is True


def test_start_health_server_custom_host_binds_all_interfaces():
    """start_health_server passes the custom host to ThreadingHTTPServer when host is 0.0.0.0."""
    monitor = HealthMonitor()

    with patch("http.server.ThreadingHTTPServer") as mock_http_server_cls:
        mock_http_server_cls.return_value = MagicMock()
        start_health_server(monitor, port=8000, host="0.0.0.0")

    bind_address = mock_http_server_cls.call_args[0][0]
    assert bind_address == ("0.0.0.0", 8000)


@pytest.mark.slow
@pytest.mark.database
def test_health_monitor_check_db_with_real_postgres(pg_engine):
    """check_db executes SELECT 1 against a live PostgreSQL instance and returns True."""
    monitor = HealthMonitor(db_engine=pg_engine)
    assert monitor.check_db() is True
    # get_status should also reflect a reachable database
    status = monitor.get_status()
    assert status["database"] == "reachable"


def test_start_health_server_end_to_end():
    """start_health_server binds a real socket and serves HTTP.

    /health returns 200 with a JSON body
    and an unknown path returns 404.
    Shutdown gracefully stops the server and joins the thread.
    """
    import socket
    import time
    import urllib.error
    import urllib.request

    monitor = HealthMonitor()

    # Ask the OS for a free port, then release it so ThreadingHTTPServer can bind to it.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    result = start_health_server(monitor, port=port, host="127.0.0.1")
    assert isinstance(result, HealthServer)
    assert result.thread.daemon is True
    assert result.thread.is_alive()

    # Retry up to 1 second for serve_forever() to start processing requests.
    health_url = f"http://127.0.0.1:{port}/health"
    response_data = None
    for _ in range(20):
        try:
            with urllib.request.urlopen(health_url, timeout=1) as resp:
                assert resp.status == 200
                response_data = json.loads(resp.read())
            break
        except (urllib.error.URLError, ConnectionRefusedError, TimeoutError, OSError):
            time.sleep(0.05)
    assert response_data is not None, "Health server did not respond in time"
    assert response_data["status"] == "healthy"

    # Unknown path must return 404 (exercises the else branch of do_GET)
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/unknown", timeout=1)
    assert exc_info.value.code == 404

    # Graceful shutdown: thread must stop and socket must be released
    result.shutdown()
    assert not result.thread.is_alive()


def test_start_health_server_raises_on_port_in_use(monkeypatch):
    """start_health_server raises RuntimeError and logs via cli.fail when the port is taken."""
    import socket

    from kivoll_worker.common import health as health_mod

    fail_messages: list[str] = []
    monkeypatch.setattr(health_mod.cli, "fail", lambda msg: fail_messages.append(msg))
    monkeypatch.setattr(health_mod, "log_error", lambda *args, **kwargs: None)

    monitor = HealthMonitor()

    # Occupy a port so HTTPServer cannot bind to it.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    occupied_port = sock.getsockname()[1]
    sock.listen(1)

    try:
        with pytest.raises(RuntimeError) as exc_info:
            start_health_server(monitor, port=occupied_port, host="127.0.0.1")
    finally:
        sock.close()

    assert str(occupied_port) in str(exc_info.value)
    assert fail_messages, "cli.fail should have been called"
    assert str(occupied_port) in fail_messages[0]
