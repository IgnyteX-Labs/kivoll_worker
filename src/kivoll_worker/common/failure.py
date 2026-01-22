"""
Error tracking and logging for kivoll_worker.

This module provides persistent error logging to a JSON file. When errors occur
during scraping or scheduling, they are recorded with:
  - Timestamp
  - Exception type and message
  - Context string (e.g., "weather:fetch:api_error")
  - Fatal flag (whether the error stopped execution)

The error log is useful for debugging issues in production where logs may not
be easily accessible, and for tracking error frequency over time.

Architecture:
    Errors are stored in `data/errors.json` as a JSON array. The file has a
    version field for future migrations. If the file becomes corrupted, it
    is automatically reset to the default (empty) state.

Usage:
    >>> from kivoll_worker.common.failure import init_errors_db, log_error
    >>> init_errors_db()  # Call once at startup
    >>> try:
    ...     risky_operation()
    ... except SomeError as e:
    ...     log_error(e, "module:function:error_type", fatal=False)

Note:
    init_errors_db() is called automatically by the argument parsing in
    `kivoll_worker.common.arguments`.
"""

import logging
from importlib.resources import files
from time import time

from cliasi import Cliasi
from singlejson import JSONDeserializationError, JSONFile, load

from . import config

# CLI instance for error-related logging (always verbose)
cli = Cliasi("ERROR", messages_stay_in_one_line=False)

# The JSONFile instance managing errors.json
_errors: JSONFile

# Current schema version for the errors file
CURRENT_ERRORS_VERSION: int = 1


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def init_errors_db() -> None:
    """
    Initialize the error tracking database.

    Loads (or creates) the errors.json file from the data directory.
    If the file is corrupted, it is reset to the default empty state.

    This function is called automatically during CLI argument parsing,
    so most code doesn't need to call it directly.
    """
    global _errors

    _errors = load(
        config.data_dir() / "errors.json",
        default_data=(
            files("kivoll_worker.defaults") / "errors.default.json"
        ).read_text(),
        strict=True,
        load_file=False,  # We'll load manually to handle errors
        preserve=True,
    )

    try:
        _errors.reload()
    except JSONDeserializationError:
        # File exists but contains invalid JSON
        cli.fail(
            f"errors.json at {config.data_dir() / 'errors.json'} is malformed JSON.\n"
            f"Will save copy and create new file."
        )
        # TODO: backup malformed file before overwriting
        cli.animate_message_blocking(
            "errors.json is malformed. Restoring default database!", 3
        )
        _errors.restore_default(False)


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def __default_file() -> None:
    """
    Reset the errors file to its default (empty) state.

    Shows a countdown to allow the user to cancel with Ctrl+C.
    """
    global _errors
    cli.animate_message_blocking(
        "Writing default errors file to disk...",
        3,
        message_right="[CTRL-C to cancel]",
    )
    _errors.restore_default()
    cli.warn("Errors file reverted to default.")


def __errors_migrations() -> None:
    """
    Run migrations on the errors file if the version is outdated.

    Currently no migrations are needed, but this structure allows for
    future schema changes (e.g., adding new fields to error records).
    """
    global CURRENT_ERRORS_VERSION
    version = _errors.json["file"]["version"]
    try:
        version = int(version)
        match version:
            # Add future migrations here as new cases

            case _ if version == CURRENT_ERRORS_VERSION:
                cli.success(
                    f"Errors file version {version} is up to date.",
                    verbosity=logging.DEBUG,
                )
                return
            case _:
                cli.fail(
                    f"Errors file version {version} is unknown. Maybe too new?\n"
                    f"Will revert to default Errors file."
                )
                __default_file()
                return
    except ValueError:
        cli.fail(
            f"Errors file version is not an integer (got {version})\n"
            f"Will revert to default Errors file."
        )
        __default_file()
        return
    except KeyError:
        cli.fail(
            "errors.json is malformed, missing 'file.version' key\n"
            "Will revert to default Errors file."
        )
        __default_file()
        return


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def log_error(exception: Exception, context: str, fatal: bool) -> None:
    """
    Log an error to the persistent error database.

    Args:
        exception: The exception that occurred.
        context: A colon-separated context string describing where the error
                 occurred (e.g., "weather:fetch:api_timeout").
        fatal: Whether this error caused the operation to fail completely.

    Example:
        >>> try:
        ...     response = requests.get(url)
        ... except requests.Timeout as e:
        ...     log_error(e, "kletterzentrum:fetch:timeout", fatal=True)
    """
    global _errors

    _errors.json["errors"].append(
        {
            "timestamp": int(time()),
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "context": context,
            "fatal": fatal,
        }
    )

    _errors.save()
