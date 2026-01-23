from importlib.resources import files

from sqlalchemy import create_engine, text

from kivoll_worker import storage


def _migration_ids() -> set[str]:
    return {
        p.name
        for p in files("kivoll_worker.storage.migrations").iterdir()
        if p.name.endswith(".sql")
    }


def test_apply_migrations_creates_tables_and_records() -> None:
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        storage._apply_migrations(conn)
        applied = {
            row[0] for row in conn.execute(text("SELECT id FROM migrations")).fetchall()
        }
        assert applied == _migration_ids()

        table_names = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        assert "weather_hourly" in table_names
        assert "kletterzentrum_data" in table_names


def test_apply_migrations_is_idempotent() -> None:
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        storage._apply_migrations(conn)
        count_before = conn.execute(
            text("SELECT COUNT(*) FROM migrations")
        ).scalar_one()
        storage._apply_migrations(conn)
        count_after = conn.execute(text("SELECT COUNT(*) FROM migrations")).scalar_one()
        assert count_before == count_after


def test_apply_migration_skips_empty_file() -> None:
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        storage._ensure_migrations_table(conn)
        storage._apply_migration(conn, "  \n", "0000_empty.sql", "empty")
        count = conn.execute(text("SELECT COUNT(*) FROM migrations")).scalar_one()
        assert count == 0
