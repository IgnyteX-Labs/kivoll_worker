from argparse import Namespace
from datetime import time

import pytest

from kivoll_worker import scraper


class _DummyCli:
    def __init__(self) -> None:
        self.failed: list[str] = []
        self.warned: list[str] = []
        self.logged: list[str] = []

    def fail(self, msg: str, *args, **kwargs) -> None:
        self.failed.append(msg)

    def warn(self, msg: str, *args, **kwargs) -> None:
        self.warned.append(msg)

    def log(self, msg: str, *args, **kwargs) -> None:
        self.logged.append(msg)

    def info(self, msg: str, *args, **kwargs) -> None:
        self.logged.append(msg)

    def success(self, msg: str, *args, **kwargs) -> None:
        self.logged.append(msg)


def test_parse_time_of_day_valid() -> None:
    cli = _DummyCli()
    parsed = scraper._parse_time_of_day("14:30", cli)
    assert parsed == time(14, 30)


def test_parse_time_of_day_invalid_reports_failure(monkeypatch) -> None:
    cli = _DummyCli()
    monkeypatch.setattr(scraper, "log_error", lambda *args, **kwargs: None)
    with pytest.raises(ValueError):
        scraper._parse_time_of_day("not-a-time", cli)
    assert cli.failed


def test_is_open_includes_start_excludes_end() -> None:
    info = {"open": (time(9, 0), time(22, 0))}
    assert scraper._is_open(time(9, 0), info) is True
    assert scraper._is_open(time(21, 59), info) is True
    assert scraper._is_open(time(22, 0), info) is False


def test_resolve_targets_all_includes_all(monkeypatch) -> None:
    cli = _DummyCli()
    monkeypatch.setattr(scraper, "log_error", lambda *args, **kwargs: None)
    resolved = scraper._resolve_targets("all,unknown,weather", time(10, 0), cli)
    assert resolved == ["weather", "kletterzentrum"]
    assert any("Unknown target" in msg for msg in cli.warned)


def test_resolve_targets_auto_selection_respects_open_hours() -> None:
    cli = _DummyCli()
    resolved = scraper._resolve_targets(None, time(23, 0), cli)
    assert resolved == ["weather"]


def test_main_partial_failure_exit_code(monkeypatch) -> None:
    args = Namespace(list_targets=False, time_of_day=None, targets="alpha,beta")
    monkeypatch.setattr(scraper, "parse_scrape_args", lambda: args)
    monkeypatch.setattr(scraper, "init_db", lambda: None)
    monkeypatch.setattr(scraper, "_reference_time", lambda *args, **kwargs: time(10, 0))
    monkeypatch.setattr(
        scraper,
        "SCRAPE_TARGETS",
        {
            "alpha": {"run": lambda _args: True},
            "beta": {"run": lambda _args: False},
        },
    )
    assert scraper.main() == 1
