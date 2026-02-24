import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

import niquests
import pytest
from niquests.adapters import HTTPAdapter

from kivoll_worker.scrape import session as session_mod


def _disable_retries(s: niquests.Session) -> None:
    """Remount adapters with max_retries=0 so timeouts surface immediately as
    ``niquests.exceptions.Timeout`` instead of being wrapped in ``ConnectionError``
    after the retry budget is exhausted."""
    s.mount("http://", HTTPAdapter(max_retries=0))
    s.mount("https://", HTTPAdapter(max_retries=0))


@contextmanager
def _slow_server() -> Generator[int, None, None]:
    """Start an HTTP server that sleeps 10 s before responding; yield the port."""

    class _SlowHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # pragma: no cover - exercised by integration test
            time.sleep(10.0)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"too late")

        def log_message(self, format, *args):
            return

    server = HTTPServer(("", 0), _SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


# ---------------------------------------------------------------------------
# Unit tests – session configuration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make_session",
    [
        lambda _: session_mod.create_scrape_session(),
        lambda tmp: session_mod.create_cached_scrape_session(cache_expire_after=60),
    ],
    ids=["plain", "cached"],
)
def test_session_retries_configuration(tmp_path, make_session) -> None:
    """Both session factories configure a RetryConfiguration with the expected values."""
    s = make_session(tmp_path)
    assert isinstance(s.retries, niquests.RetryConfiguration)
    assert s.retries.total == 3
    assert s.retries.backoff_factor == 0
    assert s.retries.status_forcelist == [429, 500, 502, 503, 504]
    assert set(s.retries.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert s.retries.respect_retry_after_header is True


@pytest.mark.parametrize(
    "make_session",
    [
        lambda _: session_mod.create_scrape_session(),
        lambda tmp: session_mod.create_cached_scrape_session(cache_expire_after=60),
    ],
    ids=["plain", "cached"],
)
def test_session_has_timeout(tmp_path, make_session) -> None:
    """Both session factories set session.timeout to DEFAULT_TIMEOUT."""
    s = make_session(tmp_path)
    assert s.timeout == session_mod.DEFAULT_TIMEOUT


def test_set_timeout_property_sets_default_timeout() -> None:
    """set_timeout_property correctly sets session.timeout on a bare session."""
    s = niquests.Session()
    session_mod.set_timeout_property(s)
    assert s.timeout == session_mod.DEFAULT_TIMEOUT


# ---------------------------------------------------------------------------
# Shared server infrastructure for integration tests
# ---------------------------------------------------------------------------


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


@contextmanager
def _test_server(responses: list[tuple]) -> Generator[tuple[str, int], None, None]:
    """Context manager that starts an HTTP server and yields (url_base, port).

    Automatically handles server startup, provides the server details, and ensures
    proper cleanup (shutdown and thread join) on exit.

    Args:
        responses: List of (status, body, headers) tuples to serve in order

    Yields:
        Tuple of (url_base, port) where url_base is "http://127.0.0.1:{port}"
    """
    handler_cls = _ControlledHandler
    handler_cls.responses = list(responses)
    handler_cls.recorded_paths = []

    server = HTTPServer(("", 0), handler_cls)

    def _serve() -> None:
        try:
            server.serve_forever()
        except (KeyboardInterrupt, SystemExit):
            # Expected when server.shutdown() is called from the main thread
            pass

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()

    port = server.server_address[1]
    url_base = f"http://127.0.0.1:{port}"

    try:
        yield url_base, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.network
def test_retry_and_cache_integration(tmp_path) -> None:
    """Integration test: server will first return 2x 500 errors, then a 200.

    The session should retry up to the configured number of attempts and
    eventually return the 200 body. Then a cached session should return a cached
    response even if the server later returns 500.
    """
    # Prepare server: two 500 responses, then a 200 response
    responses = [
        (500, "server error 1", {}),
        (500, "server error 2", {}),
        (200, "final-ok", {"Content-Type": "text/plain"}),
    ]

    with _test_server(responses) as (url_base, port):
        url = f"{url_base}/test"

        # Non-cached session: should retry and eventually get 'final-ok'
        s = session_mod.create_scrape_session()
        resp = s.get(url)
        assert resp.status_code == 200
        assert resp.text == "final-ok"

    # Now test caching: create a cached session with an on-disk cache in tmp_path
    cache_name = str(tmp_path / "cachedb")

    # Start a fresh server that returns 200 first, then 500
    responses2 = [
        (200, "cached-body", {"Content-Type": "text/plain"}),
        (500, "later-500", {}),
    ]

    with _test_server(responses2) as (url_base2, port2):
        url2 = f"{url_base2}/cachetest"

        cs = session_mod.create_cached_scrape_session(
            cache_expire_after=60, cache_name=cache_name
        )
        r1 = cs.get(url2)
        assert r1.status_code == 200
        assert r1.text == "cached-body"

    # New session using same cache should return cached response even though server is down
    cs2 = session_mod.create_cached_scrape_session(
        cache_expire_after=60, cache_name=cache_name
    )
    r2 = cs2.get(url2)
    assert r2.status_code == 200
    assert r2.text == "cached-body"


@pytest.mark.slow
@pytest.mark.network
def test_retry_stops_after_max_attempts() -> None:
    """Verify that retries stop after TOTAL_RETRIES attempts and don't continue infinitely.

    The session should make exactly 1 initial attempt + 3 retries = 4 total requests
    when the server keeps returning 500 errors, then raise a RetryError.
    This proves the retry mechanism is finite and won't loop forever.
    """
    # Prepare server to return many 500 errors (more than the retry limit)
    # We'll return 10 errors to ensure we have more than enough to exceed the limit
    responses = [(500, f"server error {i}", {}) for i in range(10)]

    with _test_server(responses) as (url_base, port):
        url = f"{url_base}/test-retry-limit"

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
        except niquests.exceptions.RetryError:
            pass

        # CRITICAL: Verify exactly 4 requests were made (1 initial + 3 retries)
        # This proves the retry mechanism stops and doesn't continue infinitely
        assert len(_ControlledHandler.recorded_paths) == 4, (
            f"Expected exactly 4 requests (1 initial + 3 retries), "
            f"but got {len(_ControlledHandler.recorded_paths)}: {_ControlledHandler.recorded_paths}"
        )
        assert all(
            path == "/test-retry-limit" for path in _ControlledHandler.recorded_paths
        )


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.parametrize(
    "make_session",
    [
        lambda tmp_path: session_mod.create_scrape_session(),
        lambda tmp_path: session_mod.create_cached_scrape_session(
            cache_expire_after=60, cache_name=str(tmp_path / "cache")
        ),
    ],
    ids=["plain", "cached"],
)
def test_session_times_out_when_server_is_slow(tmp_path, make_session) -> None:
    """Verify that session.timeout is enforced for both session types.

    The timeout is overridden to a very small value so the test completes quickly.
    Retries are disabled so the first read-timeout surfaces immediately as
    ``niquests.exceptions.Timeout`` rather than being wrapped in ``ConnectionError``
    after the retry budget is exhausted.
    """
    SHORT_TIMEOUT = 0.05  # 50 ms

    with _slow_server() as port:
        s = make_session(tmp_path)
        s.timeout = SHORT_TIMEOUT
        _disable_retries(s)

        with pytest.raises(niquests.exceptions.Timeout):
            s.get(f"http://127.0.0.1:{port}/slow")
