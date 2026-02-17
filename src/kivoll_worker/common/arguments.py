"""
Command-line argument parsing for kivoll_worker entry points.

This module provides argument parsing helpers for each CLI entry point:
- :func:`parse_schedule_args` for ``kivoll-schedule``
- :func:`parse_scrape_args` for ``kivoll-scrape``

Each parser adds the shared options ``--verbose``, ``--warn-only``, and
``--config-path`` before initializing configuration and error tracking.

Example::
    >>> from kivoll_worker.common.arguments import parse_scrape_args
    >>> args = parse_scrape_args()
    >>> if args.dry_run:
    ...     print("Running in dry-run mode")
"""

import argparse
import logging
import os

from cliasi import cli

from kivoll_worker import __version__

# ---------------------------------------------------------------------------
# Common Argument Handling
# ---------------------------------------------------------------------------


def _parse_common_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """
    Add shared CLI options, parse arguments, and perform runtime initialization.

    :param parser:
        ArgumentParser instance with entry-point specific options already defined.
    :returns: Parsed arguments namespace.
    :rtype: argparse.Namespace
    """
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enable verbose mode for this run.",
    )
    parser.add_argument(
        "--warn-only",
        dest="warn_only",
        action="store_true",
        default=False,
        help="Only display warnings and errors (overrides --verbose).",
    )
    parser.add_argument(
        "--config-path",
        dest="config_path",
        action="store",
        default="data/config.json",
        help="Path to main config file (default: data/config.json)",
    )
    parser.add_argument(
        "--db-host",
        dest="db_host",
        type=str,
        default=None,
        help="Database host URL (overrides environment variable DB_HOST)",
    )
    parser.add_argument(
        "--worker-password",
        dest="worker_password",
        type=str,
        default=None,
        help="Worker user password "
        "(overrides environment variable WORKER_APP_PASSWORD)",
    )
    parser.add_argument(
        "--migrator-password",
        dest="migrator_password",
        type=str,
        default=None,
        help="Migrator user password "
        "(overrides environment variable WORKER_MIGRATOR_PASSWORD)",
    )
    parser.add_argument(
        "--scheduler-password",
        dest="scheduler_password",
        type=str,
        default=None,
        help="Scheduler password "
        "(overrides environment variable SCHEDULER_DB_PASSWORD)",
    )

    args = parser.parse_args()

    # Initialize configuration system with the specified config file
    from .config import init_config

    init_config(args.config_path)

    # Initialize error tracking database
    from .failure import init_errors_db

    init_errors_db()

    # Configure CLI output verbosity
    cli.messages_stay_in_one_line = not args.verbose
    cli.min_verbose_level = (
        logging.WARNING
        if args.warn_only
        else logging.DEBUG
        if args.verbose
        else logging.INFO
    )

    # Get variables from the environment
    db_host = os.environ.get("DB_HOST")
    scheduler_password = os.environ.get("SCHEDULER_DB_PASSWORD")
    worker_password = os.environ.get("WORKER_APP_PASSWORD")
    migrator_password = os.environ.get("WORKER_MIGRATOR_PASSWORD")

    if args.db_host and (db_host_arg := args.db_host.strip()):
        db_host = db_host_arg

    if args.scheduler_password and (
        scheduler_password_arg := args.scheduler_password.strip()
    ):
        scheduler_password = scheduler_password_arg

    if args.worker_password and (worker_password_arg := args.worker_password.strip()):
        worker_password = worker_password_arg

    if args.migrator_password and (
        migrator_password_arg := args.migrator_password.strip()
    ):
        migrator_password = migrator_password_arg

    # Validate and set defaults for required credentials
    credentials = {
        "db_host": (db_host, "DB_HOST", "localhost:5432"),
        "scheduler_password": (
            scheduler_password,
            "SCHEDULER_DB_PASSWORD",
            "schedulerpass",
        ),
        "worker_password": (
            worker_password,
            "WORKER_APP_PASSWORD",
            "workerpass",
        ),
        "migrator_password": (
            migrator_password,
            "WORKER_MIGRATOR_PASSWORD",
            "workermigratorpass",
        ),
    }

    for var_name, (value, env_var, default) in credentials.items():
        # Check if value is None, empty, or whitespace-only
        is_empty = value is None or (isinstance(value, str) and not value.strip())

        if is_empty:
            cli.warn(
                f"{env_var} is not set. \n"
                f"Will use default value '{default}', which may not work if"
                f" the database is configured with a different password or host."
            )
            cli.warn(
                f"Change environment variables "
                f"or use the --{env_var.replace('_', '-').lower()} argument."
            )
            args.__setattr__(var_name, default)
        else:
            # Use the actual value (already stripped if it came from CLI args)
            args.__setattr__(var_name, value)

    return args


# ---------------------------------------------------------------------------
# Entry Point Parsers
# ---------------------------------------------------------------------------


def parse_schedule_args() -> argparse.Namespace:
    """
    Parse arguments for the ``kivoll-schedule`` entry point.

    This parser only exposes the shared arguments, as the scheduler runs continuously.

    :returns: Parsed arguments namespace.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        prog="kivoll-schedule",
        description="Kletterzentrum Innsbruck Auslastungsmonitor - job scheduler",
    )
    return _parse_common_args(parser)


def parse_scrape_args() -> argparse.Namespace:
    """
    Parse arguments for the ``kivoll-scrape`` entry point.

    Scrape-specific arguments:
    - ``--dry-run``: Skip live data fetching.
    - ``--targets``: Comma-separated target list (``weather, kletterzentrum, all``).
    - ``--time-of-day``: Simulate running at a specific HH:MM time.
    - ``--list-targets``: List available targets and exit.

    :returns: Parsed arguments including scrape-specific options.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        prog="kivoll-scrape",
        description="Fetch and parse occupancy/weather data from configured sources",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Do a dry run "
        "(don't request data from the website or run expensive actions)",
    )
    parser.add_argument(
        "--targets",
        dest="targets",
        type=str,
        default=None,
        help="Comma-separated scrape targets to run. Use 'all' to run all targets. "
        "When omitted, selects targets that are marked open at the reference time.",
    )
    parser.add_argument(
        "--time-of-day",
        dest="time_of_day",
        type=str,
        default=None,
        help="Run all targets that are open at specified (HH:MM) time",
    )
    parser.add_argument(
        "--list-targets",
        dest="list_targets",
        action="store_true",
        default=False,
        help="List available targets and their respective open hours",
    )
    return _parse_common_args(parser)
