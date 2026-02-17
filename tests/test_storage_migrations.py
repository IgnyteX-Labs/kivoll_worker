from argparse import Namespace
from importlib.resources import files

import psycopg
import pytest
from sqlalchemy import text

from kivoll_worker import storage


def _migration_ids() -> set[str]:
    return {
        p.name
        for p in files("kivoll_worker.storage.migrations").iterdir()
        if p.name.endswith(".sql")
    }


def _engine_from_session(session):
    # Session is bound to a Connection in tests; use its Engine for new conns.
    bind = session.get_bind()
    return bind.engine


def _ensure_worker_db(host: str, port: int, test_env: dict[str, str]) -> None:
    admin_user = test_env["POSTGRES_USER"]
    admin_password = test_env["POSTGRES_PASSWORD"]
    admin_db = test_env["POSTGRES_DB"]

    def _ensure_roles_and_db(conn) -> None:
        worker_app_password = test_env["WORKER_APP_PASSWORD"]
        worker_migrator_password = test_env["WORKER_MIGRATOR_PASSWORD"]
        if not conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = 'worker_migrator'"
        ).fetchone():
            conn.execute(
                f"CREATE ROLE worker_migrator LOGIN PASSWORD '{worker_migrator_password}'"
            )
        if not conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = 'worker_app'"
        ).fetchone():
            conn.execute(
                f"CREATE ROLE worker_app LOGIN PASSWORD '{worker_app_password}'"
            )
        if not conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'worker_db'"
        ).fetchone():
            conn.execute("CREATE DATABASE worker_db")
        conn.execute("GRANT ALL PRIVILEGES ON DATABASE worker_db TO worker_migrator")
        conn.execute("GRANT CONNECT ON DATABASE worker_db TO worker_app")

    with psycopg.connect(
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        dbname=admin_db,
        autocommit=True,
    ) as conn:
        _ensure_roles_and_db(conn)

    with psycopg.connect(
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        dbname="worker_db",
        autocommit=True,
    ) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS public")
        conn.execute("GRANT USAGE, CREATE ON SCHEMA public TO worker_migrator")
        conn.execute("GRANT USAGE ON SCHEMA public TO worker_app")
        conn.execute(
            """
            ALTER DEFAULT PRIVILEGES FOR ROLE worker_migrator IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO worker_app
            """
        )


@pytest.mark.slow
@pytest.mark.database
def test_connect_accepts_storage(db_engine) -> None:
    engine = _engine_from_session(db_engine)
    storage_obj = storage.Storage(engine)

    with storage.connect(storage_obj) as conn:
        assert conn.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.slow
@pytest.mark.database
def test_connect_accepts_engine(db_engine) -> None:
    engine = _engine_from_session(db_engine)

    with storage.connect(engine) as conn:
        assert conn.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.slow
@pytest.mark.database
def test_storage_connect_creates_connection(db_engine) -> None:
    engine = _engine_from_session(db_engine)
    storage_obj = storage.Storage(engine)

    with storage_obj.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.slow
@pytest.mark.database
def test_apply_migrations_creates_tables_and_records(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    storage._apply_migrations(session.connection())
    applied = {
        row[0] for row in session.execute(text("SELECT id FROM migrations")).fetchall()
    }
    assert applied == _migration_ids()

    table_names = {
        row[0]
        for row in session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).fetchall()
    }
    assert "weather_hourly" in table_names
    assert "kletterzentrum_data" in table_names


@pytest.mark.slow
@pytest.mark.database
def test_apply_migrations_is_idempotent(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    storage._apply_migrations(session.connection())
    count_before = session.execute(text("SELECT COUNT(*) FROM migrations")).scalar_one()
    storage._apply_migrations(session.connection())
    count_after = session.execute(text("SELECT COUNT(*) FROM migrations")).scalar_one()
    assert count_before == count_after


@pytest.mark.slow
@pytest.mark.database
def test_apply_migration_skips_empty_file(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    storage._ensure_migrations_table(session.connection())

    storage._apply_migration(session.connection(), "  \n", "0000_empty.sql", "empty")
    count = session.execute(text("SELECT COUNT(*) FROM migrations")).scalar_one()
    assert count == 0


@pytest.mark.slow
@pytest.mark.database
def test_init_db_returns_storage_and_applies_migrations(test_db, test_env) -> None:
    host = test_db.get_container_host_ip()
    port = int(test_db.get_exposed_port(5432))
    _ensure_worker_db(host, port, test_env)

    args = Namespace(
        db_host=f"{host}:{port}",
        migrator_password=test_env["WORKER_MIGRATOR_PASSWORD"],
        worker_password=test_env["WORKER_APP_PASSWORD"],
    )

    storage_obj = storage.init_db(args)
    assert isinstance(storage_obj, storage.Storage)

    with storage_obj.connect() as conn:
        applied = {
            row[0] for row in conn.execute(text("SELECT id FROM migrations")).fetchall()
        }
    assert applied == _migration_ids()


@pytest.mark.slow
@pytest.mark.database
def test_apply_migration_failure_raises_and_does_not_record(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    storage._ensure_migrations_table(session.connection())

    with pytest.raises(Exception):  # noqa:B017
        storage._apply_migration(
            session.connection(),
            "CREATE TABLE broken_table (id INT;",
            "0001_broken.sql",
            "broken",
        )

    session.rollback()
    storage._ensure_migrations_table(session.connection())
    count = session.execute(
        text("SELECT COUNT(*) FROM migrations WHERE id = '0001_broken.sql'")
    ).scalar_one()
    assert count == 0
