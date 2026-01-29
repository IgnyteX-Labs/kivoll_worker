from argparse import Namespace
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError
from sqlalchemy.exc import SQLAlchemyError

from kivoll_worker.scrape import kletterzentrum


def test_kletterzentrum_dry_run_success(
    mock_kletterzentrum_cliasi,
    dummy_cli,
    mock_kletterzentrum_config,
    monkeypatch,
    tmp_path,
):
    """Test dry run mode with existing cached HTML file."""
    args = Namespace(dry_run=True)
    # Set mock config
    monkeypatch.setattr(kletterzentrum, "config", mock_kletterzentrum_config)
    # Create cached file
    html = "<html>Test</html>"
    (tmp_path / "last_request.html").write_text(html, encoding="utf-8")

    mock_conn = Mock()
    result = kletterzentrum.kletterzentrum(args, mock_conn)
    assert result is True
    # Check that the warning was issued (message contains "cached HTML")
    assert len(dummy_cli.warned) > 0 and "cached HTML" in dummy_cli.warned[0]


def test_kletterzentrum_dry_run_no_cache(
    mock_kletterzentrum_cliasi,
    dummy_cli,
    mock_kletterzentrum_config,
    mock_kletterzentrum_log_error,
    monkeypatch,
    tmp_path,
):
    """Test dry run mode without cached HTML file raises FileNotFoundError."""
    args = Namespace(dry_run=True)
    monkeypatch.setattr(kletterzentrum, "config", mock_kletterzentrum_config)

    mock_conn = Mock()
    with pytest.raises(FileNotFoundError):
        kletterzentrum.kletterzentrum(args, mock_conn)


def test_kletterzentrum_successful_fetch_and_store(
    mock_kletterzentrum_cliasi,
    dummy_cli,
    mock_kletterzentrum_config,
    mock_kletterzentrum_get_tz,
    mock_kletterzentrum_log_error,
    monkeypatch,
    tmp_path,
):
    """Test successful fetch and store of kletterzentrum data."""
    args = Namespace(dry_run=False)
    monkeypatch.setattr(kletterzentrum, "config", mock_kletterzentrum_config)
    monkeypatch.setattr(kletterzentrum, "__short_version__", "1.0")

    # Mock requests
    mock_response = Mock()
    mock_response.text = """
    <html>
      <body>
        <h2>Overall 50%</h2>
      </body>
    </html>
    """
    mock_response.raise_for_status = Mock()

    # Mock db
    mock_conn = Mock()
    mock_conn.execute = Mock()

    with patch(
        "kivoll_worker.scrape.kletterzentrum.requests.get",
        return_value=mock_response,
    ):
        result = kletterzentrum.kletterzentrum(args, mock_conn)

    assert result is True
    mock_conn.execute.assert_called_once()


def test_kletterzentrum_http_error(
    mock_kletterzentrum_cliasi,
    dummy_cli,
    mock_kletterzentrum_config,
    mock_kletterzentrum_log_error,
    monkeypatch,
    tmp_path,
):
    """Test handling of HTTP errors during fetch."""
    args = Namespace(dry_run=False)
    monkeypatch.setattr(kletterzentrum, "config", mock_kletterzentrum_config)
    monkeypatch.setattr(kletterzentrum, "__short_version__", "1.0")

    # Mock requests to raise HTTPError
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError("HTTP Error")

    with patch(
        "kivoll_worker.scrape.kletterzentrum.requests.get",
        return_value=mock_response,
    ):
        result = kletterzentrum.kletterzentrum(args, Mock())

    assert result is False
    assert len(dummy_cli.failed) > 0 and "Could not fetch data" in dummy_cli.failed[0]


def test_kletterzentrum_config_error_url(
    mock_kletterzentrum_cliasi, dummy_cli, mock_kletterzentrum_log_error, monkeypatch
):
    """Test config error when URL is missing."""
    args = Namespace(dry_run=False)
    # Mock config without url
    mock_config = Mock()
    mock_config.config.return_value = {"modules": {"kletterzentrum": {}}}
    monkeypatch.setattr(kletterzentrum, "config", mock_config)

    result = kletterzentrum.kletterzentrum(args, Mock())
    assert result is False
    assert len(dummy_cli.failed) > 0 and "Could not retrieve url" in dummy_cli.failed[0]


def test_kletterzentrum_config_error_user_agent(
    mock_kletterzentrum_cliasi,
    dummy_cli,
    mock_kletterzentrum_config,
    mock_kletterzentrum_get_tz,
    mock_kletterzentrum_log_error,
    monkeypatch,
    tmp_path,
):
    """Test config error when user agent is missing, but succeeds with default."""
    args = Namespace(dry_run=False)
    # Mock config without user_agent
    mock_config = Mock()
    mock_config.config.return_value = {
        "modules": {"kletterzentrum": {"url": "http://example.com"}}
    }
    mock_config.data_dir.return_value = tmp_path
    monkeypatch.setattr(kletterzentrum, "config", mock_config)
    monkeypatch.setattr(kletterzentrum, "__short_version__", "1.0")

    # Mock requests
    mock_response = Mock()
    mock_response.text = "<html></html>"
    mock_response.raise_for_status = Mock()

    with patch(
        "kivoll_worker.scrape.kletterzentrum.requests.get",
        return_value=mock_response,
    ):
        result = kletterzentrum.kletterzentrum(args, Mock())

    assert result is True  # Should succeed with default UA


def test_kletterzentrum_db_error(
    mock_kletterzentrum_cliasi,
    dummy_cli,
    mock_kletterzentrum_config,
    mock_kletterzentrum_get_tz,
    mock_kletterzentrum_log_error,
    monkeypatch,
    tmp_path,
):
    """Test handling of database errors during store."""
    args = Namespace(dry_run=False)
    monkeypatch.setattr(kletterzentrum, "config", mock_kletterzentrum_config)
    monkeypatch.setattr(kletterzentrum, "__short_version__", "1.0")

    # Mock requests
    mock_response = Mock()
    mock_response.text = """
    <html>
      <body>
        <h2>Overall 50%</h2>
      </body>
    </html>
    """
    mock_response.raise_for_status = Mock()

    # Mock db to raise error
    mock_conn = Mock()
    mock_conn.execute.side_effect = SQLAlchemyError("DB Error")

    with patch(
        "kivoll_worker.scrape.kletterzentrum.requests.get",
        return_value=mock_response,
    ):
        result = kletterzentrum.kletterzentrum(args, mock_conn)

    assert result is False
    assert (
        len(dummy_cli.failed) > 0
        and "Could not store kletterzentrum data" in dummy_cli.failed[0]
    )


def test_kletterzentrum_parsing_failure(
    mock_kletterzentrum_cliasi,
    dummy_cli,
    mock_kletterzentrum_config,
    mock_kletterzentrum_get_tz,
    mock_kletterzentrum_log_error,
    monkeypatch,
    tmp_path,
):
    """Test parsing failure with invalid HTML, but still succeeds."""
    args = Namespace(dry_run=False)
    monkeypatch.setattr(kletterzentrum, "config", mock_kletterzentrum_config)
    monkeypatch.setattr(kletterzentrum, "__short_version__", "1.0")

    # Mock requests with invalid HTML
    mock_response = Mock()
    mock_response.text = "<html>Invalid</html>"
    mock_response.raise_for_status = Mock()

    mock_conn = Mock()

    with patch(
        "kivoll_worker.scrape.kletterzentrum.requests.get",
        return_value=mock_response,
    ):
        result = kletterzentrum.kletterzentrum(args, mock_conn)

    assert result is True  # Parsing succeeds even with invalid HTML
