"""
Database storage and migration management for kivoll_worker.

This module provides:
  - SQLite/PostgreSQL database connection management
  - Automatic SQL migration system for schema versioning
  - Connection pooling via SQLAlchemy

The migration system scans `kivoll_worker/storage/migrations/*.sql` for migration
files. Each file is applied once and recorded in the `migrations` table to prevent
re-application.

Migration files should be named with a numeric prefix for ordering:
    0001_initial_weather.sql
    0002_initial_kletterzentrum.sql
    0003_add_indexes.sql

Environment Variables:
    - WORKER_DB_URL: Database connection URL (default: sqlite:///data/kivoll.sqlite3)
                     For PostgreSQL: postgresql+psycopg://user:pass@host:port/dbname

Example:
    >>> from kivoll_worker.storage import init_db, connect
    >>> init_db()  # Apply pending migrations
    >>> with connect() as conn:
    ...     result = conn.execute(text("SELECT * FROM weather_hourly"))
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from cliasi import Cliasi
from sqlalchemy import Connection, Engine, create_engine, text

from ..common import config

# CLI instance for database-related logging (reinitialized in init_db)
cli: Cliasi = Cliasi("uninitialized")

# Database connection URL from environment (for Docker/production use)
# Falls back to SQLite file in data directory if not set
db_host = os.environ.get("DB_HOST")
db_password = os.environ.get("WORKER_DB_PASSWORD")
db_driver = os.environ.get("DB_DRIVER")

# Default SQLite database filename
DATABASE_FILE = "kivoll.sqlite3"

# Cached SQLAlchemy engine (lazily initialized)
_engine: Engine | None = None


# ---------------------------------------------------------------------------
# Migration Table Management
# ---------------------------------------------------------------------------


def _ensure_migrations_table(conn: Connection) -> None:
    """
    Create the migrations tracking table if it doesn't exist.

    The migrations table stores:
      - id: Unique identifier (filename) for each applied migration
      - filename: Original filename of the migration
      - applied_at: ISO 8601 timestamp when the migration was applied
    """
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


def _get_applied_migrations(conn: Connection) -> set[str]:
    """Return the set of migration IDs that have already been applied."""
    cur = conn.execute(text("SELECT id FROM migrations"))
    return {row[0] for row in cur.fetchall()}


def _apply_migration(
    conn: Connection, migration: str, filepath: str, name: str
) -> None:
    """
    Apply a single SQL migration file.

    Args:
        conn: Database connection.
        migration: SQL content of the migration file.
        filepath: Path/name of the migration file (used as ID).
        name: Human-readable name (usually the file stem).

    Raises:
        Exception: If the migration fails (transaction is rolled back).
    """
    if not migration.strip():
        cli.log(f"Skipping empty migration file {filepath}")
        return

    cli.log(f"Applying SQL migration {filepath}")
    try:
        # Execute each statement separately (split by semicolons)
        for statement in migration.split(";"):
            stmt = statement.strip()
            if not stmt:
                continue
            conn.execute(text(stmt))

        # Record the migration as applied
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
    """
    Apply all pending SQL migrations from the storage/migrations directory.

    Migrations are loaded from the packaged `kivoll_worker.storage.migrations`
    resource directory. Each .sql file is applied in alphabetical order, and
    recorded in the `migrations` table to prevent re-application.
    """
    _ensure_migrations_table(conn)
    applied = _get_applied_migrations(conn)

    # Load and sort migration files from package resources
    migrations = sorted(
        [
            x
            for x in files("kivoll_worker.storage.migrations").iterdir()
            if Path(x.name).suffix == ".sql"
        ],
        key=lambda p: p.name,
    )

    cli.log("Found migrations: " + ", ".join(m.name for m in migrations))

    pending_count = len(migrations) - len(applied)
    if pending_count > 0:
        cli.info(
            "Applying database migrations...",
            message_right=f"[{pending_count} pending]",
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_db() -> None:
    """
    Initialize the database connection and apply pending migrations.

    This should be called once at application startup before any database
    operations. It:
      1. Establishes a connection to the database
      2. Creates the migrations table if needed
      3. Applies any pending SQL migrations
    """
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
    """
    Get or create the SQLAlchemy engine.

    The engine is lazily created on first access and cached for reuse.
    Uses WORKER_DB_URL environment variable if set, otherwise falls back
    to a SQLite database in the configured data directory.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(
            f"postgresql+psycopg://worker:{db_password}@{db_host}/worker_db"
            if db_host and db_password and db_driver == "postgresql"
            else "sqlite:///" + str(config.data_dir() / DATABASE_FILE)
        )
    return _engine


def connect() -> Connection:
    """
    Get a new database connection.

    Returns:
        Connection: A new SQLAlchemy connection to the database.

    Note:
        The caller is responsible for closing the connection when done,
        preferably using a context manager:
        >>> with connect() as conn:
        ...     conn.execute(...)
    """
    return _ensure_engine().connect()


# Minimal public API
__all__ = [
    "init_db",
    "connect",
]
