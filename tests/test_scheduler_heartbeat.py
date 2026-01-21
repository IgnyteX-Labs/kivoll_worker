from datetime import datetime, timedelta, timezone
from pathlib import Path

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


class _DummyScheduler:
    def __init__(self, jobs: list[_DummyJob], tz=timezone.utc) -> None:
        self._jobs = jobs
        self.timezone = tz

    def get_jobs(self) -> list[_DummyJob]:
        return self._jobs


def test_heartbeat_writes_min_next_run(monkeypatch, tmp_path: Path) -> None:
    next_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    later_time = next_time + timedelta(minutes=10)
    sched = _DummyScheduler(
        [_DummyJob(_DummyTrigger(later_time)), _DummyJob(_DummyTrigger(next_time))]
    )
    monkeypatch.setattr(sched_mod, "_heartbeat_path", lambda: tmp_path / "heartbeat")

    sched_mod.heartbeat(sched)

    assert (tmp_path / "heartbeat").read_text() == next_time.isoformat()


def test_heartbeat_removes_when_no_jobs(monkeypatch, tmp_path: Path) -> None:
    hb = tmp_path / "heartbeat"
    hb.write_text("stale")
    sched = _DummyScheduler([])
    monkeypatch.setattr(sched_mod, "_heartbeat_path", lambda: hb)

    sched_mod.heartbeat(sched)

    assert not hb.exists()
