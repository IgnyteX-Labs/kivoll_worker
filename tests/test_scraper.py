from argparse import Namespace
from datetime import time
from unittest import mock

import pytest

from kivoll_worker import scraper


def test_parse_time_of_day_valid(dummy_cli):
    """Test parsing valid time of day string."""
    parsed = scraper._parse_time_of_day("14:30", dummy_cli)
    assert parsed == time(14, 30)


def test_parse_time_of_day_invalid_reports_failure(dummy_cli, mock_scraper_log_error):
    """Test parsing invalid time of day reports failure."""
    with pytest.raises(ValueError):
        scraper._parse_time_of_day("not-a-time", dummy_cli)
    assert dummy_cli.failed


def test_reference_time_with_override(dummy_cli, mock_scraper_get_tz):
    """Test reference time with explicit override."""
    ref = scraper._reference_time("15:45", dummy_cli)
    assert ref == time(15, 45)
    assert any("Using provided time of day" in msg for msg in dummy_cli.logged)


def test_reference_time_current_time(dummy_cli, mock_scraper_get_tz, monkeypatch):
    """Test reference time using current time when none provided."""
    monkeypatch.setattr("kivoll_worker.scraper.datetime", mock.Mock())
    mock_datetime = mock.Mock()
    mock_datetime.now.return_value.time.return_value = time(12, 0)
    with mock.patch("kivoll_worker.scraper.datetime", mock_datetime):
        ref = scraper._reference_time(None, dummy_cli)
    assert ref == time(12, 0)
    assert any("Using current time" in msg for msg in dummy_cli.logged)


def test_is_open_includes_start_excludes_end():
    """Test _is_open function boundaries."""
    info = {"open": (time(9, 0), time(22, 0))}
    assert scraper._is_open(time(9, 0), info) is True
    assert scraper._is_open(time(21, 59), info) is True
    assert scraper._is_open(time(22, 0), info) is False


def test_is_open_no_restriction():
    """Test _is_open with no restrictions."""
    info = {}
    assert scraper._is_open(time(23, 0), info) is True


def test_open_targets():
    """Test _open_targets returns correct targets based on time."""
    # Assuming weather is always open, kletterzentrum only during 9-22
    assert "weather" in scraper._open_targets(time(23, 0))
    assert "kletterzentrum" not in scraper._open_targets(time(23, 0))
    assert "kletterzentrum" in scraper._open_targets(time(10, 0))


def test_resolve_targets_all_includes_all(dummy_cli, mock_scraper_log_error):
    """Test resolving 'all' targets includes valid ones and warns about unknown."""
    resolved = scraper._resolve_targets("all,unknown,weather", time(10, 0), dummy_cli)
    assert resolved == ["weather", "kletterzentrum"]
    assert any("Unknown target" in msg for msg in dummy_cli.warned)


def test_resolve_targets_auto_selection_respects_open_hours(dummy_cli):
    """Test auto-selection of targets respects open hours."""
    resolved = scraper._resolve_targets(None, time(23, 0), dummy_cli)
    assert resolved == ["weather"]
    assert any("No explicit targets supplied" in msg for msg in dummy_cli.logged)


def test_resolve_targets_empty_selections(dummy_cli, mock_scraper_log_error):
    """Test resolving only unknown targets results in empty list."""
    resolved = scraper._resolve_targets("unknown1,unknown2", time(10, 0), dummy_cli)
    assert resolved == []
    assert any("No valid targets requested" in msg for msg in dummy_cli.warned)


def test_main_list_targets(mock_scraper_cliasi, dummy_cli, monkeypatch):
    """Test main function with list_targets flag."""
    args = Namespace(list_targets=True, time_of_day=None, targets=None)
    monkeypatch.setattr(scraper, "parse_scrape_args", lambda: args)
    result = scraper.main()
    assert result == 0
    assert any("Listing available targets" in msg for msg in dummy_cli.informed)


def test_main_time_resolution_failure(
    mock_scraper_cliasi,
    dummy_cli,
    mock_scraper_init_db,
    mock_scraper_log_error,
    monkeypatch,
):
    """Test main function fails on invalid time resolution."""
    args = Namespace(list_targets=False, time_of_day="invalid", targets=None)
    monkeypatch.setattr(scraper, "parse_scrape_args", lambda: args)
    result = scraper.main()
    assert result == 1
    assert any("Could not resolve time of day" in msg for msg in dummy_cli.failed)


def test_main_no_targets(
    mock_scraper_cliasi, dummy_cli, mock_scraper_init_db, monkeypatch
):
    """Test main function fails when no targets are resolved."""
    args = Namespace(list_targets=False, time_of_day=None, targets=None)
    monkeypatch.setattr(scraper, "parse_scrape_args", lambda: args)
    monkeypatch.setattr(scraper, "_reference_time", lambda *args, **kwargs: time(10, 0))
    monkeypatch.setattr(scraper, "_resolve_targets", lambda *args, **kwargs: [])
    result = scraper.main()
    assert result == 1
    assert any("No targets to scrape" in msg for msg in dummy_cli.informed)


def test_main_successful_scraping(
    mock_scraper_cliasi, dummy_cli, mock_scraper_init_db, monkeypatch
):
    """Test successful scraping of targets."""
    args = Namespace(list_targets=False, time_of_day=None, targets="weather")
    monkeypatch.setattr(scraper, "parse_scrape_args", lambda: args)
    monkeypatch.setattr(scraper, "_reference_time", lambda *args, **kwargs: time(10, 0))
    monkeypatch.setattr(scraper, "connect", mock.Mock())
    mock_db = mock.Mock()
    monkeypatch.setattr(scraper, "connect", lambda: mock_db)
    # Mock weather function to return True
    with mock.patch.object(scraper, "weather", return_value=True):
        result = scraper.main()
    assert result == 0
    assert any("Scraping successful" in msg for msg in dummy_cli.succeeded)
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_main_partial_failure(
    mock_scraper_cliasi, dummy_cli, mock_scraper_init_db, monkeypatch
):
    """Test partial failure in scraping multiple targets."""
    args = Namespace(
        list_targets=False, time_of_day=None, targets="weather,kletterzentrum"
    )
    monkeypatch.setattr(scraper, "parse_scrape_args", lambda: args)
    monkeypatch.setattr(scraper, "_reference_time", lambda *args, **kwargs: time(10, 0))
    monkeypatch.setattr(scraper, "connect", mock.Mock())
    mock_db = mock.Mock()
    monkeypatch.setattr(scraper, "connect", lambda: mock_db)

    # Mock weather to succeed, kletterzentrum to fail
    def mock_weather(conn):
        return True

    def mock_kletterzentrum(args, conn):
        return False

    with (
        mock.patch.object(scraper, "weather", side_effect=mock_weather),
        mock.patch.object(scraper, "kletterzentrum", side_effect=mock_kletterzentrum),
    ):
        result = scraper.main()
    assert result == 1
    assert any("1 target(s) failed" in msg for msg in dummy_cli.warned)
    assert mock_db.commit.call_count == 1  # Only weather committed
    assert mock_db.rollback.call_count == 1  # kletterzentrum rolled back


def test_main_exception_during_scraping(
    mock_scraper_cliasi,
    dummy_cli,
    mock_scraper_init_db,
    mock_scraper_log_error,
    monkeypatch,
):
    """Test exception handling during scraping."""
    args = Namespace(list_targets=False, time_of_day=None, targets="weather")
    monkeypatch.setattr(scraper, "parse_scrape_args", lambda: args)
    monkeypatch.setattr(scraper, "_reference_time", lambda *args, **kwargs: time(10, 0))
    monkeypatch.setattr(scraper, "connect", mock.Mock())
    mock_db = mock.Mock()
    monkeypatch.setattr(scraper, "connect", lambda: mock_db)
    # Mock weather to raise exception
    with mock.patch.object(scraper, "weather", side_effect=Exception("Test error")):
        result = scraper.main()
    assert result == 1
    assert any("scrape raised an exception" in msg for msg in dummy_cli.failed)
    mock_db.rollback.assert_called_once()
    mock_db.close.assert_called_once()
