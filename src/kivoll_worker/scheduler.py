from datetime import datetime as dt

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.blocking import BlockingScheduler
from cliasi import Cliasi

from kivoll_worker.common.arguments import parse_manage_args
from kivoll_worker.common.config import get_tz
from kivoll_worker.scraper import main as scrape

DESIRED_JOBS = {
    "kletterzentrum": {
        "func": scrape,
        "trigger": "cron",
        "hour": "9-22",
        "minute": "*/5",
    },
    "weather": {
        "func": scrape,
        "trigger": "cron",
        "hour": "22-23,00-09",
        "minute": "0",
    },
}


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
    scheduler.add_jobstore(SQLAlchemyJobStore(url="sqlite:///data/jobs.sqlite3"))
    cli.log("Reconciling scheduled jobs")
    _reconcile_jobs(scheduler)
    next_run = min(
        job.trigger.get_next_fire_time(dt.now(), dt.now())
        for job in scheduler.get_jobs()
    )
    cli.success(
        f"Scheduler initialized, next run at ~{next_run}",
        messages_stay_in_one_line=False,
    )
    scheduler.start()
    return 0


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


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass

if __name__ == "__main__":
    raise SystemExit(main())
