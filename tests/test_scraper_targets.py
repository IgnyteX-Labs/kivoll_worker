from argparse import Namespace
from datetime import time
from unittest import mock

import pytest

import kivoll_worker.common.failure as failure_mod
from kivoll_worker import scraper


def test_parse_time_of_day_valid(dummy_cli) -> None:
    cli = dummy_cli
    parsed = scraper._parse_time_of_day("14:30", cli)
    assert parsed == time(14, 30)


def test_parse_time_of_day_invalid_reports_failure(dummy_cli, monkeypatch) -> None:
    cli = dummy_cli
    monkeypatch.setattr(scraper, "log_error", lambda *args, **kwargs: None)
    with pytest.raises(ValueError):
        scraper._parse_time_of_day("not-a-time", cli)
    assert cli.failed


def test_is_open_includes_start_excludes_end() -> None:
    info = {"open": (time(9, 0), time(22, 0))}
    assert scraper._is_open(time(9, 0), info) is True
    assert scraper._is_open(time(21, 59), info) is True
    assert scraper._is_open(time(22, 0), info) is False


def test_resolve_targets_all_includes_all(dummy_cli, monkeypatch) -> None:
    cli = dummy_cli
    monkeypatch.setattr(scraper, "log_error", lambda *args, **kwargs: None)
    resolved = scraper._resolve_targets("all,unknown,weather", time(10, 0), cli)
    assert resolved == ["weather", "kletterzentrum"]
    assert any("Unknown target" in msg for msg in cli.warned)


def test_resolve_targets_auto_selection_respects_open_hours(dummy_cli) -> None:
    cli = dummy_cli
    resolved = scraper._resolve_targets(None, time(23, 0), cli)
    assert resolved == ["weather"]


def test_main_partial_failure_exit_code(monkeypatch) -> None:
    args = Namespace(list_targets=False, time_of_day=None, targets="alpha,beta")
    monkeypatch.setattr(scraper, "parse_scrape_args", lambda: args)
    monkeypatch.setattr(scraper, "init_db", lambda: None)
    monkeypatch.setattr(scraper, "_reference_time", lambda *args, **kwargs: time(10, 0))
    monkeypatch.setattr(
        failure_mod, "_errors", mock.Mock(json={"errors": []}, save=mock.Mock())
    )
    monkeypatch.setattr(
        scraper,
        "SCRAPE_TARGETS",
        {
            "alpha": {"run": lambda _args, _db: True},
            "beta": {"run": lambda _args, _db: False},
        },
    )
    assert scraper.main() == 1
