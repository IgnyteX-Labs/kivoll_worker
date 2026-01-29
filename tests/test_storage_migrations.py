from importlib.resources import files

import pytest
from sqlalchemy import text

from kivoll_worker import storage


def _migration_ids() -> set[str]:
    return {
        p.name
        for p in files("kivoll_worker.storage.migrations").iterdir()
        if p.name.endswith(".sql")
    }


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


@pytest.mark.database
def test_apply_migrations_is_idempotent(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    storage._apply_migrations(session.connection())
    count_before = session.execute(text("SELECT COUNT(*) FROM migrations")).scalar_one()
    storage._apply_migrations(session.connection())
    count_after = session.execute(text("SELECT COUNT(*) FROM migrations")).scalar_one()
    assert count_before == count_after


@pytest.mark.database
def test_apply_migration_skips_empty_file(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    storage._ensure_migrations_table(session.connection())

    storage._apply_migration(session.connection(), "  \n", "0000_empty.sql", "empty")
    count = session.execute(text("SELECT COUNT(*) FROM migrations")).scalar_one()
    assert count == 0
