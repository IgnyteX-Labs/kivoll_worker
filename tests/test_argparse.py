import sys
from unittest import mock

import pytest

from kivoll_worker import __version__
from kivoll_worker.common import arguments


@pytest.fixture(autouse=True)
def mock_inits():
    """Mock initialization functions to avoid side effects in tests."""
    with (
        mock.patch("kivoll_worker.common.config.init_config"),
        mock.patch("kivoll_worker.common.failure.init_errors_db"),
    ):
        yield


def test_parse_manage_args_defaults(monkeypatch):
    """Test parse_manage_args with default arguments."""
    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])
    args = arguments.parse_manage_args()
    assert args.verbose is False
    assert args.warn_only is False
    assert args.config_path == "data/config.json"


def test_parse_manage_args_with_options(monkeypatch):
    """Test parse_manage_args with verbose and config path."""
    monkeypatch.setattr(
        sys, "argv", ["kivoll-schedule", "--verbose", "--config-path", "custom.json"]
    )
    args = arguments.parse_manage_args()
    assert args.verbose is True
    assert args.warn_only is False
    assert args.config_path == "custom.json"


def test_parse_manage_args_warn_only(monkeypatch):
    """Test parse_manage_args with warn-only."""
    monkeypatch.setattr(sys, "argv", ["kivoll-schedule", "--warn-only"])
    args = arguments.parse_manage_args()
    assert args.verbose is False
    assert args.warn_only is True
    assert args.config_path == "data/config.json"


def test_parse_scrape_args_defaults(monkeypatch):
    """Test parse_scrape_args with default arguments."""
    monkeypatch.setattr(sys, "argv", ["kivoll-scrape"])
    args = arguments.parse_scrape_args()
    assert args.verbose is False
    assert args.warn_only is False
    assert args.config_path == "data/config.json"
    assert args.dry_run is False
    assert args.targets is None
    assert args.time_of_day is None
    assert args.list_targets is False


def test_parse_scrape_args_with_scrape_options(monkeypatch):
    """Test parse_scrape_args with scrape-specific options."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kivoll-scrape",
            "--dry-run",
            "--targets",
            "weather,kletterzentrum",
            "--time-of-day",
            "14:30",
            "--list-targets",
            "--verbose",
        ],
    )
    args = arguments.parse_scrape_args()
    assert args.verbose is True
    assert args.warn_only is False
    assert args.config_path == "data/config.json"
    assert args.dry_run is True
    assert args.targets == "weather,kletterzentrum"
    assert args.time_of_day == "14:30"
    assert args.list_targets is True


def test_parse_predict_args_defaults(monkeypatch):
    """Test parse_predict_args with default arguments."""
    monkeypatch.setattr(sys, "argv", ["kivoll-predict"])
    args = arguments.parse_predict_args()
    assert args.verbose is False
    assert args.warn_only is False
    assert args.config_path == "data/config.json"
    assert args.model is None
    assert args.input is None


def test_parse_predict_args_with_options(monkeypatch):
    """Test parse_predict_args with model and input."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kivoll-predict",
            "--model",
            "model.pkl",
            "--input",
            "data.csv",
            "--warn-only",
        ],
    )
    args = arguments.parse_predict_args()
    assert args.verbose is False
    assert args.warn_only is True
    assert args.config_path == "data/config.json"
    assert args.model == "model.pkl"
    assert args.input == "data.csv"


# ---------------------------------------------------------------------------
# Version Argument Tests
# ---------------------------------------------------------------------------


def test_parse_manage_args_version(monkeypatch, capsys):
    """Test that --version displays version and exits for kivoll-schedule."""
    monkeypatch.setattr(sys, "argv", ["kivoll-schedule", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        arguments.parse_manage_args()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "kivoll-schedule" in captured.out
    assert __version__ in captured.out


def test_parse_scrape_args_version(monkeypatch, capsys):
    """Test that --version displays version and exits for kivoll-scrape."""
    monkeypatch.setattr(sys, "argv", ["kivoll-scrape", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        arguments.parse_scrape_args()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "kivoll-scrape" in captured.out
    assert __version__ in captured.out


def test_parse_predict_args_version(monkeypatch, capsys):
    """Test that --version displays version and exits for kivoll-predict."""
    monkeypatch.setattr(sys, "argv", ["kivoll-predict", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        arguments.parse_predict_args()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "kivoll-predict" in captured.out
    assert __version__ in captured.out


# ---------------------------------------------------------------------------
# Credentials and Environment Variable Tests
# ---------------------------------------------------------------------------


def test_env_vars_loaded_into_args(monkeypatch):
    """Test that environment variables are loaded into args attributes."""
    # Set environment variables
    monkeypatch.setenv("DB_HOST", "localhost:5432")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "sched_pass")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "worker_pass")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "migrator_pass")

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])
    args = arguments.parse_manage_args()

    assert args.db_host == "localhost:5432"
    assert args.scheduler_password == "sched_pass"
    assert args.worker_password == "worker_pass"
    assert args.migrator_password == "migrator_pass"


def test_cli_args_override_env_vars(monkeypatch):
    """Test that CLI arguments override environment variables."""
    # Set environment variables
    monkeypatch.setenv("DB_HOST", "env_host:5432")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "env_sched")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "env_worker")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "env_migrator")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kivoll-schedule",
            "--db-host",
            "cli_host:5432",
            "--scheduler-password",
            "cli_sched",
            "--worker-password",
            "cli_worker",
            "--migrator-password",
            "cli_migrator",
        ],
    )
    args = arguments.parse_manage_args()

    # CLI arguments should override environment variables
    assert args.db_host == "cli_host:5432"
    assert args.scheduler_password == "cli_sched"
    assert args.worker_password == "cli_worker"
    assert args.migrator_password == "cli_migrator"


def test_whitespace_trimming_in_cli_args(monkeypatch):
    """Test that whitespace is trimmed from CLI arguments."""
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("SCHEDULER_DB_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_APP_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_MIGRATOR_PASSWORD", raising=False)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kivoll-schedule",
            "--db-host",
            "  host_with_spaces  ",
            "--worker-password",
            "  pass_with_spaces  ",
        ],
    )
    args = arguments.parse_manage_args()

    assert args.db_host == "host_with_spaces"
    assert args.worker_password == "pass_with_spaces"


def test_default_values_when_nothing_set(monkeypatch):
    """Test that default values are used when no env vars or CLI args are provided."""
    # Clear environment variables
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("SCHEDULER_DB_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_APP_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_MIGRATOR_PASSWORD", raising=False)

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        args = arguments.parse_manage_args()

        # Check that defaults are set
        assert args.db_host == "localhost:5432"
        assert args.scheduler_password == "schedulerpass"
        assert args.worker_password == "workerpass"
        assert args.migrator_password == "workermigratorpass"

        # Check that 4 warnings were issued (one for each missing credential)
        assert mock_warn.call_count == 8  # 2 warnings per credential


def test_warnings_for_missing_db_host(monkeypatch):
    """Test that warning is issued when DB_HOST is not set."""
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("SCHEDULER_DB_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_APP_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_MIGRATOR_PASSWORD", raising=False)

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        _ = arguments.parse_manage_args()

        # Check that DB_HOST warning was issued
        warn_calls = [call[0][0] for call in mock_warn.call_args_list]
        assert any("DB_HOST" in call for call in warn_calls)


def test_warnings_for_missing_scheduler_password(monkeypatch):
    """Test that warning is issued when SCHEDULER_DB_PASSWORD is not set."""
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("SCHEDULER_DB_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_APP_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_MIGRATOR_PASSWORD", raising=False)

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        _ = arguments.parse_manage_args()

        # Check that SCHEDULER_DB_PASSWORD warning was issued
        warn_calls = [call[0][0] for call in mock_warn.call_args_list]
        assert any("SCHEDULER_DB_PASSWORD" in call for call in warn_calls)


def test_warnings_for_missing_worker_password(monkeypatch):
    """Test that warning is issued when WORKER_APP_PASSWORD is not set."""
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("SCHEDULER_DB_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_APP_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_MIGRATOR_PASSWORD", raising=False)

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        _ = arguments.parse_manage_args()

        # Check that WORKER_APP_PASSWORD warning was issued
        warn_calls = [call[0][0] for call in mock_warn.call_args_list]
        assert any("WORKER_APP_PASSWORD" in call for call in warn_calls)


def test_warnings_for_missing_migrator_password(monkeypatch):
    """Test that warning is issued when WORKER_MIGRATOR_PASSWORD is not set."""
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("SCHEDULER_DB_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_APP_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_MIGRATOR_PASSWORD", raising=False)

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        _ = arguments.parse_manage_args()

        # Check that WORKER_MIGRATOR_PASSWORD warning was issued
        warn_calls = [call[0][0] for call in mock_warn.call_args_list]
        assert any("WORKER_MIGRATOR_PASSWORD" in call for call in warn_calls)


def test_no_warnings_when_env_vars_set(monkeypatch):
    """Test that no warnings are issued when all credentials are set."""
    monkeypatch.setenv("DB_HOST", "localhost:5432")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "sched_pass")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "worker_pass")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "migrator_pass")

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        _ = arguments.parse_manage_args()

        # No warnings should be issued
        assert mock_warn.call_count == 0


def test_no_warnings_when_cli_args_set(monkeypatch):
    """Test that no warnings are issued when CLI arguments are provided."""
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("SCHEDULER_DB_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_APP_PASSWORD", raising=False)
    monkeypatch.delenv("WORKER_MIGRATOR_PASSWORD", raising=False)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kivoll-schedule",
            "--db-host",
            "localhost:5432",
            "--scheduler-password",
            "sched_pass",
            "--worker-password",
            "worker_pass",
            "--migrator-password",
            "migrator_pass",
        ],
    )

    with mock.patch("cliasi.cli.warn") as mock_warn:
        _ = arguments.parse_manage_args()

        # No warnings should be issued
        assert mock_warn.call_count == 0


def test_empty_string_treated_as_missing(monkeypatch):
    """Test that empty strings are treated as missing credentials."""
    monkeypatch.setenv("DB_HOST", "")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "")

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        args = arguments.parse_manage_args()

        # Check that defaults are set for empty strings
        assert args.db_host == "localhost:5432"
        assert args.scheduler_password == "schedulerpass"
        assert args.worker_password == "workerpass"
        assert args.migrator_password == "workermigratorpass"

        # Warnings should be issued for all
        assert mock_warn.call_count == 8  # 2 warnings per credential


def test_whitespace_only_treated_as_missing(monkeypatch):
    """Test that whitespace-only strings are treated as missing credentials."""
    monkeypatch.setenv("DB_HOST", "   ")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "   ")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "   ")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "   ")

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        args = arguments.parse_manage_args()

        # Check that defaults are set for whitespace-only strings
        assert args.db_host == "localhost:5432"
        assert args.scheduler_password == "schedulerpass"
        assert args.worker_password == "workerpass"
        assert args.migrator_password == "workermigratorpass"

        # Warnings should be issued for all
        assert mock_warn.call_count == 8  # 2 warnings per credential


def test_partial_credentials_set(monkeypatch):
    """Test behavior when only some credentials are set."""
    monkeypatch.setenv("DB_HOST", "localhost:5432")
    monkeypatch.delenv("SCHEDULER_DB_PASSWORD", raising=False)
    monkeypatch.setenv("WORKER_APP_PASSWORD", "worker_pass")
    monkeypatch.delenv("WORKER_MIGRATOR_PASSWORD", raising=False)

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        args = arguments.parse_manage_args()

        # Set credentials should be used
        assert args.db_host == "localhost:5432"
        assert args.worker_password == "worker_pass"

        # Missing credentials should use defaults
        assert args.scheduler_password == "schedulerpass"
        assert args.migrator_password == "workermigratorpass"

        # Only 2 warnings should be issued (for missing ones)
        assert mock_warn.call_count == 4  # 2 warnings per missing credential
