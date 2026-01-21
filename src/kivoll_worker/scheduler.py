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

DESIRED_JOBS = {
    "kletterzentrum": {
        "func": scrape,
        "trigger": "cron",
        "hour": "9-21",
        "minute": "*/5",
    },
    "weather": {
        "func": scrape,
        "trigger": "cron",
        "hour": "22-23,00-09",
        "minute": "0",
    },
}

db_url = os.environ.get("SCHEDULER_DB_URL")


def main() -> int:
    try:
        return schedule()
    except KeyboardInterrupt:
        Cliasi("scheduler", messages_stay_in_one_line=False).info(
            "Scheduler shutting down"
        )
        return 103


def schedule() -> int:
    _ = parse_manage_args()
    cli = Cliasi("scheduler")
    scheduler = BlockingScheduler(timezone=get_tz(cli))
    cli.log("Connecting to job store")
    scheduler.add_jobstore(
        SQLAlchemyJobStore(url=db_url if db_url else "sqlite:///data/jobs.sqlite3")
    )
    cli.log("Reconciling scheduled jobs")
    _reconcile_jobs(scheduler)
    scheduler.add_listener(
        lambda event: heartbeat(scheduler), EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
    )
    now = dt.now(scheduler.timezone)
    next_run = min(
        job.trigger.get_next_fire_time(now, now) for job in scheduler.get_jobs()
    )
    cli.info(
        f"Scheduler initializing, next run at ~{next_run}",
        messages_stay_in_one_line=False,
    )
    heartbeat(scheduler)
    scheduler.start()
    return 0


def heartbeat(
    scheduler: BlockingScheduler,
    event: apscheduler.events.SchedulerEvent | None = None,
) -> None:
    now = (
        dt.now(getattr(scheduler, "timezone", None))
        if getattr(scheduler, "timezone", None)
        else dt.now()
    )
    candidates = [
        job.trigger.get_next_fire_time(now, now) for job in scheduler.get_jobs()
    ]
    next_runs = [candidate for candidate in candidates if candidate is not None]
    if not next_runs:
        _heartbeat_path().unlink(missing_ok=True)
        return

    next_run = min(next_runs)
    _heartbeat_path().write_text(next_run.isoformat())


def _reconcile_jobs(scheduler: BlockingScheduler) -> None:
    """
    Ensure all needed jobs exist in the scheduler.
    :param scheduler: Scheduler to be reconciled
    """
    existing_job_ids = {job.id for job in scheduler.get_jobs()}
    desired_job_ids = set(DESIRED_JOBS.keys())

    for job_id in existing_job_ids - desired_job_ids:
        scheduler.remove_job(job_id)

    for job_id, cfg in DESIRED_JOBS.items():
        scheduler.add_job(
            cfg["func"],
            id=job_id,
            name=job_id,
            replace_existing=True,
            **{k: v for k, v in cfg.items() if k != "func"},
        )


def _heartbeat_path() -> Path:
    return data_dir() / "heartbeat"


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass

if __name__ == "__main__":
    raise SystemExit(main())
