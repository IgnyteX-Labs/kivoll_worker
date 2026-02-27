from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

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
    args = SimpleNamespace(
        scheduler_password="pass",
        db_host="dbhost",
        health_port=8000,
        health_host="127.0.0.1",
    )
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


def test_schedule_passes_health_args_to_server(monkeypatch, dummy_cli) -> None:
    """schedule() forwards health_port and health_host from args to start_health_server."""
    args = SimpleNamespace(
        scheduler_password="pass",
        db_host="dbhost",
        health_port=9999,
        health_host="0.0.0.0",
    )
    monkeypatch.setattr(sched_mod, "parse_schedule_args", lambda: args)
    monkeypatch.setattr(sched_mod, "Cliasi", lambda name: dummy_cli)
    monkeypatch.setattr(sched_mod, "get_tz", lambda cli: timezone.utc)

    class _DummyJobStore:
        def __init__(self, url: str) -> None:
            self.engine = MagicMock()

    class _DummyScheduler:
        def __init__(self, timezone) -> None:
            self.timezone = timezone

        def add_jobstore(self, *a, **kw) -> None:
            pass

        def add_listener(self, *a, **kw) -> None:
            pass

        def add_job(self, *a, **kw) -> None:
            pass

        def get_jobs(self):
            return []

        def start(self) -> None:
            raise _StartCalled()

    monkeypatch.setattr(sched_mod, "SQLAlchemyJobStore", _DummyJobStore)
    monkeypatch.setattr(sched_mod, "BlockingScheduler", _DummyScheduler)
    monkeypatch.setattr(sched_mod, "_reconcile_jobs", lambda s: None)
    monkeypatch.setattr(sched_mod, "HealthMonitor", MagicMock())

    health_server_calls: list[dict] = []

    def _capture_health_server(monitor, *, port, host):
        health_server_calls.append({"port": port, "host": host})
        return MagicMock()

    monkeypatch.setattr(sched_mod, "start_health_server", _capture_health_server)

    with pytest.raises(_StartCalled):
        sched_mod.schedule()

    assert len(health_server_calls) == 1
    assert health_server_calls[0]["port"] == 9999
    assert health_server_calls[0]["host"] == "0.0.0.0"


def _make_minimal_scheduler_env(monkeypatch, dummy_cli, start_side_effect=None):
    """
    Patch all scheduler.py collaborators with lightweight fakes.
    Returns the MagicMock standing in for the HealthServer returned by
    start_health_server so callers can assert on .shutdown().
    """
    args = SimpleNamespace(
        scheduler_password="pass",
        db_host="dbhost",
        health_port=8000,
        health_host="127.0.0.1",
    )
    monkeypatch.setattr(sched_mod, "parse_schedule_args", lambda: args)
    monkeypatch.setattr(sched_mod, "Cliasi", lambda name: dummy_cli)
    monkeypatch.setattr(sched_mod, "get_tz", lambda cli: timezone.utc)
    monkeypatch.setattr(sched_mod, "HealthMonitor", MagicMock())
    monkeypatch.setattr(sched_mod, "_reconcile_jobs", lambda s: None)

    class _DummyJobStore:
        def __init__(self, url: str) -> None:
            self.engine = MagicMock()

    class _DummyScheduler:
        def __init__(self, timezone) -> None:
            self.timezone = timezone

        def add_jobstore(self, *a, **kw) -> None:
            pass

        def add_listener(self, *a, **kw) -> None:
            pass

        def add_job(self, *a, **kw) -> None:
            pass

        def get_jobs(self):
            return []

        def start(self) -> None:
            if start_side_effect is not None:
                raise start_side_effect

    monkeypatch.setattr(sched_mod, "SQLAlchemyJobStore", _DummyJobStore)
    monkeypatch.setattr(sched_mod, "BlockingScheduler", _DummyScheduler)

    mock_health_server = MagicMock()
    monkeypatch.setattr(
        sched_mod, "start_health_server", MagicMock(return_value=mock_health_server)
    )
    return mock_health_server


def test_schedule_shuts_down_health_server_on_normal_exit(
    monkeypatch, dummy_cli
) -> None:
    """schedule() calls health_server.shutdown() and returns 0 when the scheduler exits cleanly."""
    mock_health_server = _make_minimal_scheduler_env(monkeypatch, dummy_cli)

    result = sched_mod.schedule()

    assert result == 0
    mock_health_server.shutdown.assert_called_once()


def test_schedule_shuts_down_health_server_on_keyboard_interrupt(
    monkeypatch, dummy_cli
) -> None:
    """schedule() calls health_server.shutdown() even when KeyboardInterrupt interrupts the scheduler."""
    mock_health_server = _make_minimal_scheduler_env(
        monkeypatch, dummy_cli, start_side_effect=KeyboardInterrupt()
    )

    with pytest.raises(KeyboardInterrupt):
        sched_mod.schedule()

    mock_health_server.shutdown.assert_called_once()


def test_on_job_event_listener(monkeypatch, dummy_cli) -> None:
    """_on_job_event calls record_failure on error events and update_tick on every event."""
    args = SimpleNamespace(
        scheduler_password="pass",
        db_host="dbhost",
        health_port=8000,
        health_host="127.0.0.1",
    )
    monkeypatch.setattr(sched_mod, "parse_schedule_args", lambda: args)
    monkeypatch.setattr(sched_mod, "Cliasi", lambda name: dummy_cli)
    monkeypatch.setattr(sched_mod, "get_tz", lambda cli: timezone.utc)

    class _DummyJobStore:
        def __init__(self, url: str) -> None:
            self.engine = MagicMock()

    mock_monitor = MagicMock()
    monkeypatch.setattr(
        sched_mod, "HealthMonitor", MagicMock(return_value=mock_monitor)
    )

    captured_listeners: list[tuple] = []

    class _DummyScheduler:
        def __init__(self, timezone) -> None:
            self.timezone = timezone

        def add_jobstore(self, *a, **kw) -> None:
            pass

        def add_listener(self, listener, mask: int) -> None:
            captured_listeners.append((listener, mask))

        def add_job(self, *a, **kw) -> None:
            pass

        def get_jobs(self):
            return []

        def start(self) -> None:
            raise _StartCalled()

    monkeypatch.setattr(sched_mod, "SQLAlchemyJobStore", _DummyJobStore)
    monkeypatch.setattr(sched_mod, "BlockingScheduler", _DummyScheduler)
    monkeypatch.setattr(sched_mod, "_reconcile_jobs", lambda s: None)
    monkeypatch.setattr(sched_mod, "start_health_server", MagicMock())

    with pytest.raises(_StartCalled):
        sched_mod.schedule()

    assert len(captured_listeners) == 1
    listener, mask = captured_listeners[0]
    assert mask == EVENT_JOB_EXECUTED | EVENT_JOB_ERROR

    # An error event must trigger both record_failure and update_tick.
    error_event = SimpleNamespace(code=EVENT_JOB_ERROR)
    listener(error_event)
    mock_monitor.record_failure.assert_called_once()
    mock_monitor.update_tick.assert_called_once()

    # A success event must trigger only update_tick (no additional record_failure).
    mock_monitor.reset_mock()
    success_event = SimpleNamespace(code=EVENT_JOB_EXECUTED)
    listener(success_event)
    mock_monitor.record_failure.assert_not_called()
    mock_monitor.update_tick.assert_called_once()
