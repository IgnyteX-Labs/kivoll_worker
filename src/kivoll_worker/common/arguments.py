"""
Command-line argument parsing for kivoll_worker entry points.

This module provides argument parsing helpers for each CLI entry point:
- :func:`parse_manage_args` for ``kivoll-schedule``
- :func:`parse_scrape_args` for ``kivoll-scrape``
- :func:`parse_predict_args` for ``kivoll-predict`` (future use)

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

from cliasi import cli

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

    return args


# ---------------------------------------------------------------------------
# Entry Point Parsers
# ---------------------------------------------------------------------------


def parse_manage_args() -> argparse.Namespace:
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


def parse_predict_args() -> argparse.Namespace:
    """
    Parse arguments for the ``kivoll-predict`` entry point.

    Predict-specific arguments:
    - ``--model``: Path to the trained model file.
    - ``--input``: Path to input data for prediction.

    :returns: Parsed arguments including predict-specific options.
    :rtype: argparse.Namespace

    .. note::
        This parser currently serves as a placeholder for future
        ML functionality and may gain additional options later.
    """
    parser = argparse.ArgumentParser(
        prog="kivoll-predict",
        description="Run prediction using the (future) neural network model",
    )
    parser.add_argument(
        "--model",
        dest="model",
        type=str,
        default=None,
        help="Path to model file to use for prediction",
    )
    parser.add_argument(
        "--input",
        dest="input",
        type=str,
        default=None,
        help="Path to input data file (CSV/JSON) to predict on",
    )
    return _parse_common_args(parser)
