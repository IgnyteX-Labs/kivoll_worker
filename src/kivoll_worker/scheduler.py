"""
Job scheduler for kivoll_worker scraping tasks.

This module implements a cron-based scheduler using APScheduler
to run scraping jobs at the configured intervals.
It manages periodic weather collection outside climbing hours,
Kletterzentrum occupancy scraping during opening hours,
a heartbeat file for Docker healthchecks, and persistent job storage.

Features:
    - Periodic weather data collection (outside climbing hours)
    - Kletterzentrum occupancy scraping (during opening hours)
    - Heartbeat file updates for Docker healthchecks
    - Persistent job storage in SQLite/PostgreSQL

Entry Points:
    - `kivoll-schedule`: Starts the blocking scheduler

Environment Variables:
    - `SCHEDULER_DB_URL`: Database URL for job persistence (default: sqlite:///data/jobs.sqlite3)

Example:
    $ kivoll-schedule --verbose
"""

import os
from datetime import datetime as dt
from pathlib import Path

import apscheduler.events
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.blocking import BlockingScheduler
from cliasi import Cliasi

from kivoll_worker.common.arguments import parse_manage_args
from kivoll_worker.common.config import data_dir, get_tz
from kivoll_worker.scraper import main as scrape

# ---------------------------------------------------------------------------
# Job Configuration
# ---------------------------------------------------------------------------
# Each job is defined with:
#   - func: The function to call (usually the scraper main function)
#   - trigger: APScheduler trigger type (cron, interval, etc.)
#   - Additional kwargs passed to the trigger (hour, minute, etc.)

DESIRED_JOBS = {
    # Scrape Kletterzentrum occupancy every 5 minutes during opening hours (9am-9pm)
    "kletterzentrum": {
        "func": scrape,
        "trigger": "cron",
        "hour": "9-21",
        "minute": "*/5",
    },
    # Fetch weather data once per hour during off-hours (10pm-9am)
    # Weather data changes slowly, so frequent updates aren't needed
    "weather": {
        "func": scrape,
        "trigger": "cron",
        "hour": "22-23,00-09",
        "minute": "0",
    },
}

# Database URL for persistent job storage
# In Docker, this is set via environment variable to use PostgreSQL
db_host = os.environ.get("DB_HOST")
db_password = os.environ.get("SCHEDULER_DB_PASSWORD")
db_driver = os.environ.get("DB_DRIVER")


def main() -> int:
    """
    Entry point for the `kivoll-schedule` command.

    Wraps :func:`schedule` with keyboard interrupt handling to shut down gracefully.

    :returns: 0 when the scheduler shuts down normally, 103 when interrupted.
    :rtype: int
    """
    try:
        return schedule()
    except KeyboardInterrupt:
        Cliasi("scheduler", messages_stay_in_one_line=False).info(
            "Scheduler shutting down"
        )
        return 103


def schedule() -> int:
    """
    Initialize and run the blocking scheduler.

    The scheduler performs the following steps:
    - parse CLI arguments and configure logging
    - create a :class:`BlockingScheduler` in the configured timezone
    - connect to the persistent job store and reconcile the desired jobs
    - write an initial heartbeat file and start the scheduler

    :returns: 0 for a successful run.
    :rtype: int
    """
    _ = parse_manage_args()
    cli = Cliasi("scheduler")

    # Create scheduler with configured timezone
    scheduler = BlockingScheduler(timezone=get_tz(cli))

    # Connect to persistent job store (SQLite locally, PostgreSQL in Docker)
    cli.log("Connecting to job store")
    scheduler.add_jobstore(
        SQLAlchemyJobStore(
            url=f"postgresql+psycopg://scheduler:{db_password}@{db_host}/scheduler_db"
            if db_host and db_password and db_driver == "postgresql"
            else "sqlite:///data/jobs.sqlite3"
        )
    )

    # Ensure all desired jobs exist and remove any stale ones
    cli.log("Reconciling scheduled jobs")
    _reconcile_jobs(scheduler)

    # Update heartbeat after each job execution (success or failure)
    scheduler.add_listener(
        lambda event: heartbeat(scheduler), EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
    )

    # Calculate and display next run time
    now = dt.now(scheduler.timezone)
    next_run = min(
        job.trigger.get_next_fire_time(now, now) for job in scheduler.get_jobs()
    )
    cli.info(
        f"Scheduler initializing, next run at ~{next_run}",
        messages_stay_in_one_line=False,
    )

    # Write initial heartbeat before starting
    heartbeat(scheduler)

    # Start blocking scheduler (runs until interrupted)
    scheduler.start()
    return 0


def heartbeat(
    scheduler: BlockingScheduler,
    _: apscheduler.events.SchedulerEvent | None = None,
) -> None:
    """
    Update the heartbeat file with the next scheduled run time.

    Docker healthchecks rely on this file to verify that the scheduler is active.
    When no jobs are scheduled, the file is removed so that downstream
    monitors can detect a potential issue.

    :param scheduler: APScheduler instance used to compute the next run time.
    :param _: Optional scheduler event when this function is invoked as a listener.
    :rtype: None

    .. note::
        Removing the heartbeat file indicates that there are no
        pending jobs and should be handled as a signal that the scheduler is inactive.
    """
    # Get current time in scheduler's timezone
    now = (
        dt.now(getattr(scheduler, "timezone", None))
        if getattr(scheduler, "timezone", None)
        else dt.now()
    )

    # Collect next fire times for all jobs
    candidates = [
        job.trigger.get_next_fire_time(now, now) for job in scheduler.get_jobs()
    ]
    next_runs = [candidate for candidate in candidates if candidate is not None]

    # If no jobs scheduled, remove heartbeat file
    if not next_runs:
        _heartbeat_path().unlink(missing_ok=True)
        return

    # Write the earliest next run time to the heartbeat file
    next_run = min(next_runs)
    _heartbeat_path().write_text(next_run.isoformat())


def _reconcile_jobs(scheduler: BlockingScheduler) -> None:
    """
    Ensure the scheduler exactly matches :data:`DESIRED_JOBS`.

    Jobs that are no longer defined in :data:`DESIRED_JOBS` are removed,
    while any missing jobs are added or updated.

    :param scheduler: APScheduler instance to reconcile.
    :rtype: None
    """
    existing_job_ids = {job.id for job in scheduler.get_jobs()}
    desired_job_ids = set(DESIRED_JOBS.keys())

    # Remove jobs that are no longer desired
    for job_id in existing_job_ids - desired_job_ids:
        scheduler.remove_job(job_id)

    # Add or update all desired jobs
    for job_id, cfg in DESIRED_JOBS.items():
        scheduler.add_job(
            cfg["func"],
            id=job_id,
            name=job_id,
            replace_existing=True,
            **{k: v for k, v in cfg.items() if k != "func"},
        )


def _heartbeat_path() -> Path:
    """Return the path to the heartbeat file in the data directory."""
    return data_dir() / "heartbeat"


if __name__ == "__main__":
    raise SystemExit(main())
