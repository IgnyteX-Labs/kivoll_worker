from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

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
    args = SimpleNamespace(scheduler_password="pass", db_host="dbhost")
    monkeypatch.setattr(sched_mod, "parse_schedule_args", lambda: args)
    monkeypatch.setattr(sched_mod, "Cliasi", lambda name: dummy_cli)
    monkeypatch.setattr(sched_mod, "get_tz", lambda cli: timezone.utc)

    captured: dict[str, object] = {}

    class _DummyJobStore:
        def __init__(self, url: str) -> None:
            captured["jobstore_url"] = url

    class _DummyScheduler:
        def __init__(self, timezone) -> None:
            captured["timezone"] = timezone
            self.timezone = timezone
            self.jobstore = None
            self.listeners: list[tuple[object, int]] = []
            self._jobs = [
                _DummyJob(
                    _DummyTrigger(datetime.now(timezone.utc) + timedelta(minutes=5))
                )
            ]
            self.started = False

        def add_jobstore(self, jobstore) -> None:
            self.jobstore = jobstore

        def add_listener(self, listener, mask: int) -> None:
            self.listeners.append((listener, mask))

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

    heartbeat_calls: list[object] = []

    def _heartbeat(scheduler, *_args) -> None:
        heartbeat_calls.append(scheduler)

    monkeypatch.setattr(sched_mod, "heartbeat", _heartbeat)

    with pytest.raises(_StartCalled):
        sched_mod.schedule()

    assert captured["timezone"] == timezone.utc
    assert captured["jobstore_url"] == (
        "postgresql+psycopg://scheduler:pass@dbhost/scheduler_db"
    )
    assert reconcile_called and isinstance(reconcile_called[0], _DummyScheduler)
    assert heartbeat_calls == [reconcile_called[0]]
    assert reconcile_called[0].listeners
    assert reconcile_called[0].started is True
