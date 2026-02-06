import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import niquests

from kivoll_worker.scrape import session as session_mod


def test_default_session_retries_configuration() -> None:
    """Ensure create_scrape_session sets a RetryConfiguration with the expected values."""
    s = session_mod.create_scrape_session()
    assert isinstance(s.retries, niquests.RetryConfiguration)
    # Compare the important fields we set in set_reties_property
    assert s.retries.total == 3
    assert s.retries.backoff_factor == 0
    assert s.retries.status_forcelist == [429, 500, 502, 503, 504]
    assert set(s.retries.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert s.retries.respect_retry_after_header is True


def test_cached_session_retries_configuration() -> None:
    """Ensure create_cached_scrape_session sets the same RetryConfiguration."""
    cs = session_mod.create_cached_scrape_session(cache_expire_after=60)
    assert isinstance(cs.retries, niquests.RetryConfiguration)
    assert cs.retries.total == 3
    assert cs.retries.backoff_factor == 0
    assert cs.retries.status_forcelist == [429, 500, 502, 503, 504]
    assert set(cs.retries.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert cs.retries.respect_retry_after_header is True


class _ControlledHandler(BaseHTTPRequestHandler):
    # Shared state across handler instances
    responses: list[tuple] = []  # list of (status, body, headers)
    recorded_paths: list[str] = []

    def do_GET(self) -> None:  # pragma: no cover - exercised by integration test
        _ControlledHandler.recorded_paths.append(self.path)
        if not _ControlledHandler.responses:
            # Default: 200 OK
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        status, body, headers = _ControlledHandler.responses.pop(0)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        if isinstance(body, str):
            body = body.encode()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # silence default logging
        return


def _start_server(responses: list[tuple]) -> tuple[HTTPServer, threading.Thread]:
    """Start an HTTP server that will serve the provided responses in order."""
    handler_cls = _ControlledHandler
    handler_cls.responses = list(responses)
    handler_cls.recorded_paths = []

    server = HTTPServer(("", 0), handler_cls)

    def _serve() -> None:
        try:
            server.serve_forever()
        except Exception:
            pass

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    return server, thread


def test_retry_and_cache_integration(tmp_path) -> None:
    """Integration test: server will first return 2x 500 errors, then a 200.

    The session should retry up to the configured number of attempts and
    eventually return the 200 body. Then a cached session should return a cached
    response even if the server later returns 500.
    """
    from kivoll_worker.scrape import session as session_mod

    # Prepare server: two 500 responses, then a 200 response
    responses = [
        (500, "server error 1", {}),
        (500, "server error 2", {}),
        (200, "final-ok", {"Content-Type": "text/plain"}),
    ]
    server, thread = _start_server(responses)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/test"

    # Non-cached session: should retry and eventually get 'final-ok'
    s = session_mod.create_scrape_session()
    resp = s.get(url)
    assert resp.status_code == 200
    assert resp.text == "final-ok"

    # Now test caching: create a cached session with an on-disk cache in tmp_path
    cache_name = str(tmp_path / "cachedb")
    # Prime the cache: first request will be successful (server already used 3 responses), so to ensure cache we insert a 200 response first
    # Restart server to return 200 first, then 500 to prove cache serving on subsequent call
    server.shutdown()
    thread.join(timeout=1)

    # Start a fresh server that returns 200 first, then 500
    responses2 = [
        (200, "cached-body", {"Content-Type": "text/plain"}),
        (500, "later-500", {}),
    ]
    server2, thread2 = _start_server(responses2)
    port2 = server2.server_address[1]
    url2 = f"http://127.0.0.1:{port2}/cachetest"

    cs = session_mod.create_cached_scrape_session(
        cache_expire_after=60, cache_name=cache_name
    )
    r1 = cs.get(url2)
    assert r1.status_code == 200
    assert r1.text == "cached-body"
    # Ensure subsequent request hits cache: stop server to force cache-use
    server2.shutdown()
    thread2.join(timeout=1)

    # New session using same cache should return cached response even though server is down
    cs2 = session_mod.create_cached_scrape_session(
        cache_expire_after=60, cache_name=cache_name
    )
    r2 = cs2.get(url2)
    assert r2.status_code == 200
    assert r2.text == "cached-body"

    # Cleanup
    try:
        server2.server_close()
    except Exception:
        pass


def test_retry_stops_after_max_attempts() -> None:
    """Verify that retries stop after TOTAL_RETRIES attempts and don't continue infinitely.

    The session should make exactly 1 initial attempt + 3 retries = 4 total requests
    when the server keeps returning 500 errors, then raise a RetryError.
    This proves the retry mechanism is finite and won't loop forever.
    """
    from kivoll_worker.scrape import session as session_mod

    # Prepare server to return many 500 errors (more than the retry limit)
    # We'll return 10 errors to ensure we have more than enough to exceed the limit
    responses = [(500, f"server error {i}", {}) for i in range(10)]
    server, thread = _start_server(responses)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/test-retry-limit"

    # Clear recorded paths before test
    _ControlledHandler.recorded_paths = []

    # Create session with retry configuration (TOTAL_RETRIES = 3)
    s = session_mod.create_scrape_session()

    # Make the request - it should exhaust retries and raise RetryError
    # This proves the retry mechanism stops instead of continuing infinitely
    try:
        resp = s.get(url)
        # If we get here, the test failed - retries should have been exhausted
        raise AssertionError(
            f"Expected RetryError to be raised after exhausting retries, "
            f"but got response with status {resp.status_code}"
        )
    except niquests.exceptions.RetryError as e:
        # This is the expected behavior - retries were exhausted
        assert "Max retries exceeded" in str(e)
        assert "too many 500 error responses" in str(e)

    # CRITICAL: Verify exactly 4 requests were made (1 initial + 3 retries)
    # This proves the retry mechanism stops and doesn't continue infinitely
    assert len(_ControlledHandler.recorded_paths) == 4, (
        f"Expected exactly 4 requests (1 initial + 3 retries), "
        f"but got {len(_ControlledHandler.recorded_paths)}: {_ControlledHandler.recorded_paths}"
    )

    # All paths should be the same (our test endpoint)
    assert all(
        path == "/test-retry-limit" for path in _ControlledHandler.recorded_paths
    )

    # Cleanup
    server.shutdown()
    thread.join(timeout=1)
    try:
        server.server_close()
    except Exception:
        pass
