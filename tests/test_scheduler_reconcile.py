from __future__ import annotations

from collections.abc import Callable

from kivoll_worker import scheduler as sched_mod


class _DummyJob:
    def __init__(self, job_id: str) -> None:
        self.id = job_id


class _DummyScheduler:
    def __init__(self, job_ids: list[str]) -> None:
        self._jobs = [_DummyJob(job_id) for job_id in job_ids]
        self.removed: list[str] = []
        self.added: list[tuple[Callable[[], None], dict[str, object]]] = []

    def get_jobs(self) -> list[_DummyJob]:
        return list(self._jobs)

    def remove_job(self, job_id: str) -> None:
        self.removed.append(job_id)

    def add_job(self, func: Callable[[], None], **kwargs: object) -> None:
        self.added.append((func, kwargs))


def test_reconcile_jobs_adds_and_removes(monkeypatch) -> None:
    desired = {
        "job-a": {"func": lambda: None, "trigger": "cron", "hour": "1", "minute": "0"},
        "job-b": {"func": lambda: None, "trigger": "interval", "seconds": 30},
    }
    monkeypatch.setattr(sched_mod, "DESIRED_JOBS", desired)

    scheduler = _DummyScheduler(["job-a", "stale"])

    sched_mod._reconcile_jobs(scheduler)

    assert scheduler.removed == ["stale"]
    added_ids = {kwargs["id"] for _, kwargs in scheduler.added}
    assert added_ids == {"job-a", "job-b"}

    for _, kwargs in scheduler.added:
        assert kwargs["replace_existing"] is True
        assert kwargs["name"] == kwargs["id"]
        if kwargs["id"] == "job-a":
            assert kwargs["trigger"] == "cron"
            assert kwargs["hour"] == "1"
            assert kwargs["minute"] == "0"
        else:
            assert kwargs["trigger"] == "interval"
            assert kwargs["seconds"] == 30
