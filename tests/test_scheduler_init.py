from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from kivoll_worker import scheduler as sched_mod


class _DummyTrigger:
    def __init__(self, next_time: datetime | None) -> None:
        self._next_time = next_time

    def get_next_fire_time(
        self, _now: datetime, _reference: datetime
    ) -> datetime | None:
        return self._next_time


class _DummyJob:
    def __init__(self, trigger: _DummyTrigger) -> None:
        self.trigger = trigger


class _StartCalled(Exception):
    pass


def test_schedule_initialization(monkeypatch, dummy_cli) -> None:
    """schedule() creates the scheduler and job store with the correct parameters and starts it."""
    args = SimpleNamespace(scheduler_password="pass", db_host="dbhost")
    monkeypatch.setattr(sched_mod, "parse_schedule_args", lambda: args)
    monkeypatch.setattr(sched_mod, "Cliasi", lambda name: dummy_cli)
    monkeypatch.setattr(sched_mod, "get_tz", lambda cli: timezone.utc)

    captured: dict[str, object] = {}

    class _DummyJobStore:
        def __init__(self, url: str) -> None:
            captured["jobstore_url"] = url
            self.engine = MagicMock()

    class _DummyScheduler:
        def __init__(self, timezone) -> None:
            captured["timezone"] = timezone
            self.timezone = timezone
            self.jobstore = None
            self.jobstore_alias = None
            self.listeners: list[tuple[object, int]] = []
            self._jobs = [
                _DummyJob(
                    _DummyTrigger(datetime.now(timezone.utc) + timedelta(minutes=5))
                )
            ]
            self.started = False

        def add_jobstore(self, jobstore, alias=None) -> None:
            self.jobstore = jobstore
            self.jobstore_alias = alias

        def add_listener(self, listener, mask: int) -> None:
            self.listeners.append((listener, mask))

        def add_job(self, *args, **kwargs) -> None:
            pass

        def get_jobs(self):
            return list(self._jobs)

        def start(self) -> None:
            self.started = True
            raise _StartCalled()

    monkeypatch.setattr(sched_mod, "SQLAlchemyJobStore", _DummyJobStore)
    monkeypatch.setattr(sched_mod, "BlockingScheduler", _DummyScheduler)

    reconcile_called: list[object] = []
    monkeypatch.setattr(
        sched_mod,
        "_reconcile_jobs",
        lambda scheduler: reconcile_called.append(scheduler),
    )

    # Mock health monitor and server
    monkeypatch.setattr(sched_mod, "HealthMonitor", MagicMock())
    monkeypatch.setattr(sched_mod, "start_health_server", MagicMock())

    with pytest.raises(_StartCalled):
        sched_mod.schedule()

    assert captured["timezone"] == timezone.utc
    assert captured["jobstore_url"] == (
        "postgresql+psycopg://scheduler:pass@dbhost/scheduler_db"
    )
    assert reconcile_called and isinstance(reconcile_called[0], _DummyScheduler)
    assert reconcile_called[0].listeners
    assert reconcile_called[0].started is True
