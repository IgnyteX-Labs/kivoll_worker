from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from cliasi import Cliasi

from ..common import config

cli: Cliasi = Cliasi("uninitialized")


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS migrations
        (
            id         TEXT PRIMARY KEY,
            filename   TEXT,
            applied_at TEXT
        );
        """
    )


DATABASE_FILE = "kivoll.sqlite3"


def _get_applied_migrations(conn: sqlite3.Connection) -> set[str]:
    cur = conn.execute("SELECT id FROM migrations")
    return {row[0] for row in cur.fetchall()}


def _apply_migration(conn: sqlite3.Connection, migration: str, filepath: str) -> None:
    if not migration.strip():
        cli.log(f"Skipping empty migration file {filepath}")
        return
    cli.log(f"Applying SQL migration {filepath}")
    try:
        conn.executescript(migration)
        conn.execute(
            "INSERT INTO migrations (id, filename, applied_at) VALUES (?, ?, ?)",
            (filepath, filepath, datetime.now().isoformat()),
        )
        conn.commit()
        cli.success(f"Applied migration {filepath}")
    except Exception as e:
        conn.rollback()
        cli.fail(f"Failed to apply migration {filepath}: {e}")
        raise


def _apply_migrations(conn: sqlite3.Connection) -> None:
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
        if pathhelper.stem in applied:
            cli.log(f"Migration {pathhelper.stem} already applied, skipping")
            continue
        _apply_migration(conn, migration.read_text(encoding="utf-8"), pathhelper.stem)
    cli.success("All migrations processed", verbosity=logging.DEBUG)


def init_db() -> None:
    """Initialize DB connection and apply pending migrations."""
    global cli
    cli = Cliasi("DB")
    cli.log("Connecting to DB")
    conn = sqlite3.connect(str(config.data_dir() / DATABASE_FILE))
    try:
        cli.log("Applying pending migrations (if any)")
        _apply_migrations(conn)
        cli.success("DB initialized and migrations applied", verbosity=logging.DEBUG)
    finally:
        conn.close()


def connect() -> sqlite3.Connection:
    """Get a new DB connection."""
    return sqlite3.connect(str(config.data_dir() / DATABASE_FILE))


# Minimal public API
__all__ = [
    "init_db",
    "connect",
]
