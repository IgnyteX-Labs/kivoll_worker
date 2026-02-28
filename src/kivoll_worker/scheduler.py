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
    - Heartbeat file updates for Docker health checks
    - Persistent job storage in PostgreSQL

Entry Points:
    - `kivoll-schedule`: Starts the blocking scheduler

Environment Variables:
    - `DB_HOST`: Database URL for job persistence
    - `SCHEDULER_DB_PASSWORD`: Scheduler user password
    - variables required for kivoll-scrape

Example:
    $ kivoll-schedule --verbose
"""

from datetime import datetime as dt
from urllib.parse import quote_plus

import apscheduler.events
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.blocking import BlockingScheduler
from cliasi import Cliasi
from sqlalchemy import create_engine

from kivoll_worker.common.arguments import parse_schedule_args
from kivoll_worker.common.config import get_tz
from kivoll_worker.common.health import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    HealthMonitor,
    start_health_server,
)
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
    args = parse_schedule_args()
    cli = Cliasi("scheduler")

    # Create scheduler with configured timezone
    scheduler = BlockingScheduler(timezone=get_tz(cli))

    # Connect to persistent job store
    cli.log("Connecting to job store")
    engine = create_engine(
        url=f"postgresql+psycopg://"
        f"scheduler:{quote_plus(args.scheduler_password)}@{args.db_host}/scheduler_db"
    )
    scheduler.add_jobstore(SQLAlchemyJobStore(engine=engine))
    scheduler.add_jobstore(MemoryJobStore(), "memory")

    # Initialize health monitor
    monitor = HealthMonitor(db_engine=engine)

    # Ensure all desired jobs exist and remove any stale ones
    cli.log("Reconciling scheduled jobs")
    _reconcile_jobs(scheduler)

    # Update heartbeat after each job execution (success or failure)
    def _on_job_event(event: apscheduler.events.JobExecutionEvent) -> None:
        if event.code == EVENT_JOB_ERROR:
            monitor.record_failure()
        monitor.update_tick()

    scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # Add the health monitor task to the memory jobstore, it can't persist over restarts
    scheduler.add_job(
        monitor.update_tick,
        trigger="interval",
        seconds=DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        id="health_heartbeat",
        replace_existing=True,
        jobstore="memory",
    )

    # Start healthcheck HTTP server
    health_server = start_health_server(
        monitor, port=args.health_port, host=args.health_host
    )

    # Calculate and display next run time
    now = dt.now(scheduler.timezone)
    fire_times = [
        time
        for job in scheduler.get_jobs()
        if (time := job.trigger.get_next_fire_time(now, now)) is not None
    ]
    cli.info(
        f"Scheduler initializing, next run at ~{min(fire_times)}"
        if fire_times
        else "Scheduler initializing, could not get upcoming runs (!)",
        messages_stay_in_one_line=False,
    )

    # Start blocking scheduler (runs until interrupted).
    # try/finally guarantees health_server.shutdown() runs even when a
    # KeyboardInterrupt propagates out of start() before reaching the cleanup line.
    try:
        scheduler.start()
    finally:
        health_server.shutdown()
    return 0


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
        scheduler.remove_job(job_id, jobstore="scheduler")

    # Add or update all desired jobs in the persistent job store
    for job_id, cfg in DESIRED_JOBS.items():
        scheduler.add_job(
            cfg["func"],
            id=job_id,
            name=job_id,
            replace_existing=True,
            jobstore="scheduler",
            **{k: v for k, v in cfg.items() if k != "func"},
        )


if __name__ == "__main__":
    raise SystemExit(main())
