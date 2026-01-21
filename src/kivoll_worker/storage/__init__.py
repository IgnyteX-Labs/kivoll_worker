from __future__ import annotations

import logging
import os
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from cliasi import Cliasi
from sqlalchemy import Connection, Engine, create_engine, text

from ..common import config

cli: Cliasi = Cliasi("uninitialized")

db_url = os.environ.get("WORKER_DB_URL")
db_name = os.environ.get("DB_NAME", "db")


def _ensure_migrations_table(conn: Connection) -> None:
    conn.execute(
        text("""
        CREATE TABLE IF NOT EXISTS migrations
        (
            id         TEXT PRIMARY KEY,
            filename   TEXT,
            applied_at TEXT
        );
        """)
    )


DATABASE_FILE = "kivoll.sqlite3"

_engine: Engine | None = None


def _get_applied_migrations(conn: Connection) -> set[str]:
    cur = conn.execute(text("SELECT id FROM migrations"))
    return {row[0] for row in cur.fetchall()}


def _apply_migration(
    conn: Connection, migration: str, filepath: str, name: str
) -> None:
    if not migration.strip():
        cli.log(f"Skipping empty migration file {filepath}")
        return
    cli.log(f"Applying SQL migration {filepath}")
    try:
        for statement in migration.split(";"):
            stmt = statement.strip()
            if not stmt:
                continue
            conn.execute(text(stmt))
        conn.execute(
            text(
                "INSERT INTO migrations (id, filename, applied_at) "
                "VALUES (:filepath, :name, :applied_at)"
            ),
            {
                "filepath": filepath,
                "name": name,
                "applied_at": datetime.now().isoformat(),
            },
        )
        conn.commit()
        cli.success(f"Applied migration {filepath}")
    except Exception as e:
        conn.rollback()
        cli.fail(f"Failed to apply migration {filepath}: {e}")
        raise


def _apply_migrations(conn: Connection) -> None:
    """Apply all .sql migrations from the storage/migrations directory.
    storage/migrations is packaged with the kivoll_worker application.

    Each migration file will be recorded in the `migrations` table by its file stem.
    """
    _ensure_migrations_table(conn)
    applied = _get_applied_migrations(conn)
    migrations = sorted(
        [
            x
            for x in files("kivoll_worker.storage.migrations").iterdir()
            if Path(x.name).suffix == ".sql"
        ],
        key=lambda p: p.name,
    )
    cli.log("Found migrations: " + ", ".join(m.name for m in migrations))
    if len(migrations) > len(applied):
        cli.info(
            "Applying database migrations...",
            message_right=f"[{len(migrations) - len(applied)} pending]",
        )
    for migration in migrations:
        pathhelper = Path(migration.name)
        cli.log(f"Processing migration file {migration.name}")
        if str(pathhelper) in applied:
            cli.log(f"Migration {pathhelper.stem} already applied, skipping")
            continue
        _apply_migration(
            conn, migration.read_text(encoding="utf-8"), migration.name, pathhelper.stem
        )
    cli.success("All migrations processed", verbosity=logging.DEBUG)


def init_db() -> None:
    """Initialize DB connection and apply pending migrations."""
    global cli
    cli = Cliasi("DB")
    cli.log("Connecting to DB")
    conn = connect()
    try:
        cli.log("Applying pending migrations (if any)")
        _apply_migrations(conn)
        cli.success("DB initialized and migrations applied", verbosity=logging.DEBUG)
    finally:
        conn.close()


def _ensure_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            db_url % db_name
            if db_url
            else "sqlite:///" + str(config.data_dir() / DATABASE_FILE)
        )
    return _engine


def connect() -> Connection:
    """Get a new DB connection."""

    return _ensure_engine().connect()


# Minimal public API
__all__ = [
    "init_db",
    "connect",
]
