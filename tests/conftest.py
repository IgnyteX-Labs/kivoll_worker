import os
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.core.container import DockerContainer

# Load test environment variables
TEST_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(TEST_ENV_PATH)


@pytest.fixture(scope="session")
def test_env() -> dict[str, str]:
    """Load and return test environment variables."""
    load_dotenv(TEST_ENV_PATH)
    return {
        "POSTGRES_USER": os.getenv("POSTGRES_USER", "testadmin"),
        "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "testadminpass"),
        "POSTGRES_DB": os.getenv("POSTGRES_DB", "postgres"),
        "WORKER_APP_PASSWORD": os.getenv("WORKER_APP_PASSWORD", "workerapppassword"),
        "WORKER_MIGRATOR_PASSWORD": os.getenv(
            "WORKER_MIGRATOR_PASSWORD", "workermigratorpassword"
        ),
        "API_APP_PASSWORD": os.getenv("API_APP_PASSWORD", "apiapppassword"),
        "API_MIGRATOR_PASSWORD": os.getenv(
            "API_MIGRATOR_PASSWORD", "apimigratorpassword"
        ),
        "PREDICT_APP_PASSWORD": os.getenv("PREDICT_APP_PASSWORD", "predictapppassword"),
        "PREDICT_MIGRATOR_PASSWORD": os.getenv(
            "PREDICT_MIGRATOR_PASSWORD", "predictmigratorpassword"
        ),
        "SCHEDULER_DB_PASSWORD": os.getenv(
            "SCHEDULER_DB_PASSWORD", "schedulerdbpassword"
        ),
    }


@pytest.fixture(scope="session")
def test_db(test_env) -> Generator[DockerContainer, Any, None]:
    """Up a test DB"""
    container = _build_container("postgres:18", test_env)
    with container:
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(5432))
        _wait_for_db_ready(
            host,
            port,
            test_env["POSTGRES_USER"],
            test_env["POSTGRES_PASSWORD"],
            test_env["POSTGRES_DB"],
        )
        yield container


@pytest.fixture(scope="function")
def db_engine(
    test_db: DockerContainer, test_env: dict[str, str]
) -> Generator[Session, Any, None]:
    """Get a connection that rolls back after each test."""
    host = test_db.get_container_host_ip()
    port = int(test_db.get_exposed_port(5432))

    url = (
        f"postgresql+psycopg://"
        f"{test_env['POSTGRES_USER']}:{test_env['POSTGRES_PASSWORD']}"
        f"@{host}:{port}/{test_env['POSTGRES_DB']}"
    )

    engine = create_engine(url, future=True)
    connection = engine.connect()
    transaction = connection.begin()

    session = sessionmaker(bind=connection, future=True)()

    session.begin_nested()

    # Restart SAVEPOINT after each commit
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def _wait_for_db_ready(host: str, port: int, user: str, password: str, db: str) -> None:
    """Poll until PostgreSQL accepts connections or timeout expires."""
    deadline = time.time() + 15
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with psycopg.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=db,
                connect_timeout=5,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                return
        except Exception as exc:  # pragma: no cover - best effort polling
            last_error = exc
            time.sleep(1)
    raise TimeoutError(f"Postgres did not become ready: {last_error}")


def _build_container(image: str, test_env: dict[str, str]) -> DockerContainer:
    container = DockerContainer(image).with_exposed_ports("5432/tcp")
    for key, value in test_env.items():
        if value is not None:
            container = container.with_env(key, value)
    return container


class _DummyCli:
    def __init__(self) -> None:
        self.failed: list[str] = []
        self.warned: list[str] = []
        self.logged: list[str] = []
        self.informed: list[str] = []
        self.succeeded: list[str] = []

    def fail(self, msg: str, *args, **kwargs) -> None:
        self.failed.append(msg)
        print(f"X {msg}")  # Simulate output

    def warn(self, msg: str, *args, **kwargs) -> None:
        self.warned.append(msg)
        print(f"! {msg}")  # Simulate output

    def log(self, msg: str, *args, **kwargs) -> None:
        self.logged.append(msg)

    def info(self, msg: str, *args, **kwargs) -> None:
        self.informed.append(msg)
        print(f"i {msg}")  # Simulate output

    def success(self, msg: str, *args, **kwargs) -> None:
        self.succeeded.append(msg)
        print(f"✓ {msg}")  # Simulate output

    def animate_message_download_non_blocking(self, msg: str, **kwargs):
        from unittest.mock import Mock

        return Mock()


@pytest.fixture
def dummy_cli():
    return _DummyCli()


@pytest.fixture
def mock_cli(monkeypatch):
    from kivoll_worker.scrape import kletterzentrum

    dummy = _DummyCli()
    monkeypatch.setattr(kletterzentrum, "cli", dummy)
    return dummy


@pytest.fixture
def mock_kletterzentrum_cliasi(dummy_cli):
    from unittest.mock import patch

    with patch("kivoll_worker.scrape.kletterzentrum.Cliasi", return_value=dummy_cli):
        yield


@pytest.fixture
def mock_kletterzentrum_log_error():
    from unittest.mock import patch

    with patch(
        "kivoll_worker.scrape.kletterzentrum.log_error", lambda *args, **kwargs: None
    ):
        yield


@pytest.fixture
def mock_kletterzentrum_get_tz():
    from datetime import timezone
    from unittest.mock import patch

    with patch("kivoll_worker.scrape.kletterzentrum.get_tz", lambda cli: timezone.utc):
        yield


@pytest.fixture
def mock_kletterzentrum_config(tmp_path):
    from unittest.mock import Mock

    mock_config = Mock()
    mock_config.data_dir.return_value = tmp_path
    mock_config.config.return_value = {
        "modules": {
            "kletterzentrum": {"user_agent": "test/%s", "url": "http://example.com"}
        }
    }
    return mock_config


@pytest.fixture
def mock_scraper_cliasi(dummy_cli):
    from unittest.mock import patch

    with patch("kivoll_worker.scraper.Cliasi", lambda name: dummy_cli):
        yield


@pytest.fixture
def mock_scraper_log_error():
    from unittest.mock import patch

    with patch("kivoll_worker.scraper.log_error", lambda *args, **kwargs: None):
        yield


@pytest.fixture
def mock_scraper_get_tz():
    from unittest.mock import patch

    with patch("kivoll_worker.scraper.get_tz", lambda cli: "UTC"):
        yield


@pytest.fixture
def mock_scraper_init_db():
    from unittest.mock import patch

    with patch("kivoll_worker.scraper.init_db", lambda: None):
        yield
