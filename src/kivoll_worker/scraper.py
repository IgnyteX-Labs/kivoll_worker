"""
Main scraper orchestrator for kivoll_worker.

This module coordinates the execution of individual scraping targets
(weather and kletterzentrum) based on time-of-day rules and command line arguments.
It serves as the main entry point for manual scraping runs
and is also invoked by the scheduler.

Scrape Targets:
    - weather: Fetches weather data from the Open-Meteo API
    - kletterzentrum: Scrapes occupancy data from the Kletterzentrum Innsbruck website

Entry Points:
    - `kivoll-scrape`: Run scraping manually or for specific targets

Example::
    $ kivoll-scrape --targets=weather,kletterzentrum --verbose
    $ kivoll-scrape --list-targets
    $ kivoll-scrape  # Auto-selects targets based on current time
"""

from argparse import Namespace
from collections.abc import Callable
from datetime import datetime, time

from cliasi import Cliasi
from sqlalchemy import Connection

from kivoll_worker.common.arguments import parse_scrape_args
from kivoll_worker.common.config import get_tz
from kivoll_worker.common.failure import log_error
from kivoll_worker.scrape.kletterzentrum import kletterzentrum
from kivoll_worker.scrape.weather import weather
from kivoll_worker.storage import connect, init_db

# ---------------------------------------------------------------------------
# Scrape Target Configuration
# ---------------------------------------------------------------------------
# Each target defines its scraping function and optional time-based restrictions.
# The "open" key specifies when a target should be auto-selected (e.g., during
# business hours for kletterzentrum).

SCRAPE_TARGETS: dict[
    str, dict[str, tuple[time, time] | Callable[[Namespace, Connection], bool] | str]
] = {
    "weather": {
        "run": lambda _, connection: weather(connection),
        "interval": "0",  # Once per hour (see scheduler.py for actual cron)
    },
    "kletterzentrum": {
        "run": lambda args, connection: kletterzentrum(args, connection),
        "interval": "*/5",  # Every 5 minutes during open hours
        "open": (time(9, 0), time(22, 0)),  # Only scrape during opening hours
    },
}


# ---------------------------------------------------------------------------
# Time-of-Day Helpers
# ---------------------------------------------------------------------------


def _parse_time_of_day(raw: str, cli: Cliasi) -> time:
    """
    Parse an HH:MM formatted time string.

    :param raw: Time string provided via CLI (e.g., "14:30").
    :param cli: Cliasi instance used for logging failures.
    :returns: Parsed :class:`datetime.time` object.
    :rtype: time
    :raises ValueError: When the provided string is not a valid time.
    """
    try:
        hours, minutes = raw.split(":", maxsplit=1)
        return time(hour=int(hours), minute=int(minutes))
    except Exception as exc:  # noqa: BLE001
        cli.fail("Invalid time for --time-of-day, expected HH:MM")
        log_error(exc, "scraper:time-of-day:parse", False)
        raise


def _reference_time(time_of_day: str | None, cli: Cliasi) -> time:
    """
    Determine the reference time for selecting active targets.

    :param time_of_day: Optional CLI override in HH:MM format.
    :param cli: Cliasi instance for logging decisions.
    :returns:
        Reference :class:`datetime.time` derived from the override or the
         current time in the configured timezone.
    :rtype: time
    """
    timezone = get_tz(cli)
    if time_of_day:
        ref = _parse_time_of_day(time_of_day, cli)
        cli.log(f"Using provided time of day {ref.strftime('%H:%M')} ({timezone})")
        return ref
    now = datetime.now(timezone).time()
    cli.log(f"Using current time {now.strftime('%H:%M')} in configured timezone")
    return now


# ---------------------------------------------------------------------------
# Target Selection Logic
# ---------------------------------------------------------------------------


def _is_open(
    at: time,
    target_info: dict[
        str, tuple[time, time] | Callable[[Namespace, Connection], bool] | str
    ],
) -> bool:
    """
    Determine if a target should run at the provided time.

    :param at: Reference time for evaluation.
    :param target_info: Target configuration dictionary that may include an "open" range
    :returns: ``True`` when the target is permitted to run.
    :rtype: bool
    """
    if "open" in target_info and isinstance(target_info["open"], tuple):
        start, end = target_info["open"]
        return start <= at < end
    # No time restriction defined - always open
    return True


def _open_targets(at: time) -> list[str]:
    """Return the list of target names whose open windows include ``at``."""
    return [
        name for name in SCRAPE_TARGETS.keys() if _is_open(at, SCRAPE_TARGETS[name])
    ]


def _resolve_targets(raw_targets: str | None, at: time, cli: Cliasi) -> list[str]:
    """
    Resolve which targets to run based on CLI input or auto-selection.

    :param raw_targets: Comma-separated targets from CLI or ``None`` to auto-select.
    :param at: Reference time for auto-selection (used when ``raw_targets`` is ``None``)
    :param cli: Cliasi instance for logging warnings.
    :returns: Ordered list of target names to execute.
    :rtype: list[str]
    """
    if raw_targets is None:
        cli.log("No explicit targets supplied; selecting currently open targets")
        return _open_targets(at)

    selections: list[str] = []
    tokens = [
        token.strip().lower() for token in raw_targets.split(",") if token.strip()
    ]
    for token in tokens:
        if token == "all":
            # Add all defined targets
            for name in SCRAPE_TARGETS:
                if name not in selections:
                    selections.append(name)
            continue
        if token in SCRAPE_TARGETS and token not in selections:
            selections.append(token)
            continue
        cli.warn(f"Unknown target '{token}' will be ignored")
        log_error(
            ValueError(f"Unknown scrape target '{token}'"),
            "scraper:targets:unknown",
            False,
        )

    if not selections:
        cli.warn("No valid targets requested; nothing to do.")
    return selections


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------


def main() -> int:
    """
    Entry point for the `kivoll-scrape` command.

    Parses CLI arguments, selects targets,
    initializes the database, and runs each target's scraper.

    :returns: Exit code (0 for full success, 1 when one or more targets fail).
    :rtype: int
    """
    args = parse_scrape_args()
    cli = Cliasi("scraper")

    # Handle --list-targets flag
    if args.list_targets:
        text = "Listing available targets:"
        for name, info in SCRAPE_TARGETS.items():
            text += f"\n- {name}: {info.get('description', '')}"
        cli.info(text)
        return 0

    # Initialize database connection and run migrations
    init_db()

    # Determine reference time for target selection
    try:
        ref_time = _reference_time(args.time_of_day, cli)
    except Exception as e:
        log_error(e, "scraper:time-of-day:resolve", False)
        cli.fail("Could not resolve time of day")
        return 1

    # Resolve which targets to scrape
    targets = _resolve_targets(args.targets, ref_time, cli)
    if not targets:
        cli.info("No targets to scrape at this time.")
        return 1

    # Execute each target's scraper
    failed = 0
    total = len(targets)
    for idx, target in enumerate(targets, start=1):
        if (
            "run" in SCRAPE_TARGETS[target]
            and (runner := SCRAPE_TARGETS[target]["run"])
            and callable(runner)
        ):
            cli.info(f"Scraping {target}", message_right=f"[{idx}/{total}]")
            try:
                db = connect()
                success = runner(args, db)
                if success:
                    db.commit()
                else:
                    db.rollback()
                db.close()
            except Exception as exc:
                log_error(exc, f"scraper:run:{target}", False)
                cli.fail(
                    f"{target} scrape raised an exception: {exc}",
                    messages_stay_in_one_line=False,
                )
                db.rollback()
                db.close()
                success = False
            if not success:
                failed += 1

    # Report results
    if failed:
        cli.warn(
            f"{failed} target(s) failed, {total - failed} succeeded.",
            message_right=f"[{total}/{total}]",
        )
        return 1

    cli.success("Scraping successful.", message_right=f"[{total}/{total}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
