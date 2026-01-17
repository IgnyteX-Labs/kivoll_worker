"""
Handle command line arguments for different scripts
"""

import argparse
import logging

from cliasi import cli


def _parse_common_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """Add arguments shared across multiple scripts."""
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
        help="Path to main config file (default: config/config.json)",
    )
    args = parser.parse_args()
    from .config import init_config

    init_config(args.config_path)
    from .failure import init_errors_db

    init_errors_db()
    cli.messages_stay_in_one_line = not args.verbose
    cli.min_verbose_level = (
        logging.WARNING
        if args.warn_only
        else logging.DEBUG
        if args.verbose
        else logging.INFO
    )
    # Both values should be inferred automatically
    return args


def parse_manage_args() -> argparse.Namespace:
    """Return parsed arguments for the `kivoll_worker-manage` entry point.

    Accepts an optional argv for easier testing.
    """
    parser = argparse.ArgumentParser(
        prog="kivoll_worker-manage",
        description="Kletterzentrum Innsbruck Auslastungsmonitor - management tasks",
    )
    return _parse_common_args(parser)


def parse_scrape_args() -> argparse.Namespace:
    """Return parsed arguments for the `kivoll_worker-scrape` entry point."""
    parser = argparse.ArgumentParser(
        prog="kivoll_worker-scrape",
        description="Fetch and parse occupancy data from sources",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Do a dry run "
        "(don't request data from the website or run expensive actions)",
    )
    return _parse_common_args(parser)


def parse_predict_args() -> argparse.Namespace:
    """Return parsed arguments for the `kivoll_worker-predict` entry point.

    This is a lightweight stub; when the neural net is implemented, add more
    model/configuration-specific options here.
    """
    parser = argparse.ArgumentParser(
        prog="kivoll_worker-predict",
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
