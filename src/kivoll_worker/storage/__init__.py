"""
Database storage and migration management for kivoll_worker.

This module provides:
  - PostgreSQL database connection management
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
    - DB_HOST: Database host URL (e.g., "localhost" or "db:5432")
    - WORKER_APP_PASSWORD: Worker user password
    - WORKER_MIGRATOR_PASSWORD: Migrator user password

Example:
    >>> from kivoll_worker.storage import init_db
    >>> storage = init_db(args)  # Apply pending migrations
    >>> with storage.connect() as conn:
    ...     result = conn.execute(text("SELECT * FROM weather_hourly"))
"""

from __future__ import annotations

import logging
from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from urllib.parse import quote_plus

from cliasi import Cliasi
from sqlalchemy import Connection, Engine, create_engine, text

# CLI instance for database-related logging (reinitialized in init_db)
cli: Cliasi = Cliasi("uninitialized")


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
        cli.success(f"Applied migration {filepath}")
    except Exception as e:
        conn.rollback()
        cli.fail(
            f"Failed to apply migration {filepath}: {e}",
            messages_stay_in_one_line=False,
        )
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


@dataclass(frozen=True)
class Storage:
    """Typed wrapper around a SQLAlchemy engine."""

    engine: Engine

    def connect(self) -> Connection:
        """Get a new database connection from the engine."""
        return self.engine.connect()


def init_db(args: Namespace) -> Storage:
    """
    Initialize the database connection and apply pending migrations.

    This should be called once at application startup before any database
    operations. It:
      1. Establishes a connection to the database
      2. Creates the migrations table if needed
      3. Applies any pending SQL migrations

    :param args: Command-line arguments containing database connection info
    :returns: Storage wrapper for the worker application engine
    """
    global cli
    cli = Cliasi("DB")
    cli.log("Connecting to DB")
    # Create migrator connection
    engine = create_engine(
        f"postgresql+psycopg://"
        f"worker_migrator:{quote_plus(args.migrator_password)}@{args.db_host}/worker_db"
    )
    conn = engine.connect()
    try:
        cli.log("Applying pending migrations (if any)")
        _apply_migrations(conn)
        conn.commit()
        cli.success("DB initialized and migrations applied", verbosity=logging.DEBUG)
    finally:
        conn.close()

    app_engine = create_engine(
        f"postgresql+psycopg://"
        f"worker_app:{quote_plus(args.worker_password)}@{args.db_host}/worker_db"
    )
    return Storage(app_engine)


def connect(storage: Storage | Engine) -> Connection:
    """
    Get a new database connection from a Storage wrapper or Engine.

    Returns:
        Connection: A new SQLAlchemy connection to the database.

    Note:
        The caller is responsible for closing the connection when done,
        preferably using a context manager:
        >>> with connect(storage) as conn:
        ...     conn.execute(...)
    """
    return storage.connect()


# Minimal public API
__all__ = [
    "Storage",
    "init_db",
    "connect",
]
