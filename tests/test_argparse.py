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


@pytest.fixture(autouse=True)
def clear_credential_env(monkeypatch):
    """Ensure credential env vars do not leak into tests by default."""
    for name in (
        "DB_HOST",
        "SCHEDULER_DB_PASSWORD",
        "WORKER_APP_PASSWORD",
        "WORKER_MIGRATOR_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def set_valid_credentials(monkeypatch):
    """Set non-default credentials so parse_*_args can succeed."""
    monkeypatch.setenv("DB_HOST", "db.testing:5432")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "sched_pass")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "worker_pass")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "migrator_pass")


def test_parse_manage_args_defaults(monkeypatch, set_valid_credentials):
    """Test parse_manage_args with default arguments."""
    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])
    args = arguments.parse_schedule_args()
    assert args.verbose is False
    assert args.warn_only is False
    assert args.config_path == "data/config.json"


def test_parse_manage_args_with_options(monkeypatch, set_valid_credentials):
    """Test parse_manage_args with verbose and config path."""
    monkeypatch.setattr(
        sys, "argv", ["kivoll-schedule", "--verbose", "--config-path", "custom.json"]
    )
    args = arguments.parse_schedule_args()
    assert args.verbose is True
    assert args.warn_only is False
    assert args.config_path == "custom.json"


def test_parse_manage_args_warn_only(monkeypatch, set_valid_credentials):
    """Test parse_manage_args with warn-only."""
    monkeypatch.setattr(sys, "argv", ["kivoll-schedule", "--warn-only"])
    args = arguments.parse_schedule_args()
    assert args.verbose is False
    assert args.warn_only is True
    assert args.config_path == "data/config.json"


def test_parse_scrape_args_defaults(monkeypatch, set_valid_credentials):
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


def test_parse_scrape_args_with_scrape_options(monkeypatch, set_valid_credentials):
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


# ---------------------------------------------------------------------------
# Version Argument Tests
# ---------------------------------------------------------------------------


def test_parse_manage_args_version(monkeypatch, capsys, set_valid_credentials):
    """Test that --version displays version and exits for kivoll-schedule."""
    monkeypatch.setattr(sys, "argv", ["kivoll-schedule", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        arguments.parse_schedule_args()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "kivoll-schedule" in captured.out
    assert __version__ in captured.out


def test_parse_scrape_args_version(monkeypatch, capsys, set_valid_credentials):
    """Test that --version displays version and exits for kivoll-scrape."""
    monkeypatch.setattr(sys, "argv", ["kivoll-scrape", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        arguments.parse_scrape_args()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "kivoll-scrape" in captured.out
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
    args = arguments.parse_schedule_args()

    assert args.db_host == "localhost:5432"
    assert args.scheduler_password == "sched_pass"
    assert args.worker_password == "worker_pass"
    assert args.migrator_password == "migrator_pass"


def test_db_host_missing_uses_default(monkeypatch):
    """Test that missing DB_HOST uses default without exiting."""
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "sched_pass")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "worker_pass")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "migrator_pass")

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        args = arguments.parse_schedule_args()

    assert args.db_host == "localhost:5432"
    assert mock_warn.call_count == 1


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
    args = arguments.parse_schedule_args()

    # CLI arguments should override environment variables
    assert args.db_host == "cli_host:5432"
    assert args.scheduler_password == "cli_sched"
    assert args.worker_password == "cli_worker"
    assert args.migrator_password == "cli_migrator"


def test_whitespace_trimming_in_cli_args(monkeypatch):
    """Test that whitespace is trimmed from CLI arguments."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kivoll-schedule",
            "--db-host",
            "  host_with_spaces  ",
            "--worker-password",
            "  pass_with_spaces  ",
            "--scheduler-password",
            "sched_pass",
            "--migrator-password",
            "migrator_pass",
        ],
    )
    args = arguments.parse_schedule_args()

    assert args.db_host == "host_with_spaces"
    assert args.worker_password == "pass_with_spaces"


def test_default_values_when_nothing_set(monkeypatch):
    """Test that default values trigger exit when no env vars or CLI args."""
    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.fail") as mock_fail:
        with pytest.raises(SystemExit) as exc_info:
            arguments.parse_schedule_args()

    assert exc_info.value.code == 1
    fail_calls = [call[0][0] for call in mock_fail.call_args_list]
    assert any("SCHEDULER_DB_PASSWORD" in call for call in fail_calls)


def test_exit_when_default_value_is_provided(monkeypatch):
    """Test that providing a default credential value exits the program."""
    monkeypatch.setenv("DB_HOST", "localhost:5432")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "schedulerpass")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "worker_pass")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "migrator_pass")

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.fail") as mock_fail:
        with pytest.raises(SystemExit) as exc_info:
            arguments.parse_schedule_args()

    assert exc_info.value.code == 1
    fail_calls = [call[0][0] for call in mock_fail.call_args_list]
    assert any("SCHEDULER_DB_PASSWORD" in call for call in fail_calls)
    assert any("--allow-insecure-defaults" in call for call in fail_calls)


def test_default_value_with_allow_insecure_defaults(monkeypatch):
    """Test that default credential values are allowed with the flag."""
    monkeypatch.setenv("DB_HOST", "localhost:5432")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "schedulerpass")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "worker_pass")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "migrator_pass")

    monkeypatch.setattr(
        sys,
        "argv",
        ["kivoll-schedule", "--allow-insecure-defaults"],
    )

    with mock.patch("cliasi.cli.warn") as mock_warn:
        args = arguments.parse_schedule_args()

    assert args.scheduler_password == "schedulerpass"
    assert mock_warn.call_count == 1


def test_default_values_when_allow_insecure_defaults(monkeypatch):
    """Test that defaults are applied when allow-insecure-defaults is set."""
    monkeypatch.setattr(sys, "argv", ["kivoll-schedule", "--allow-insecure-defaults"])

    with mock.patch("cliasi.cli.warn") as mock_warn:
        args = arguments.parse_schedule_args()

    assert args.db_host == "localhost:5432"
    assert args.scheduler_password == "schedulerpass"
    assert args.worker_password == "workerpass"
    assert args.migrator_password == "workermigratorpass"
    assert mock_warn.call_count == 4


def test_partial_credentials_set(monkeypatch):
    """Test behavior when only some credentials are set."""
    monkeypatch.setenv("DB_HOST", "db.partial:5432")
    monkeypatch.delenv("SCHEDULER_DB_PASSWORD", raising=False)
    monkeypatch.setenv("WORKER_APP_PASSWORD", "worker_pass")
    monkeypatch.delenv("WORKER_MIGRATOR_PASSWORD", raising=False)

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.fail") as mock_fail:
        with pytest.raises(SystemExit) as exc_info:
            arguments.parse_schedule_args()

    assert exc_info.value.code == 1
    fail_calls = [call[0][0] for call in mock_fail.call_args_list]
    assert any("SCHEDULER_DB_PASSWORD" in call for call in fail_calls)


def test_no_warnings_when_cli_args_set(monkeypatch):
    """Test that no warnings are issued when CLI arguments are provided."""
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
        _ = arguments.parse_schedule_args()

        # No warnings should be issued
        assert mock_warn.call_count == 0


def test_empty_string_treated_as_missing(monkeypatch):
    """Test that empty strings are treated as missing credentials."""
    monkeypatch.setenv("DB_HOST", "")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "")

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.fail") as mock_fail:
        with pytest.raises(SystemExit) as exc_info:
            arguments.parse_schedule_args()

    assert exc_info.value.code == 1
    fail_calls = [call[0][0] for call in mock_fail.call_args_list]
    assert any("SCHEDULER_DB_PASSWORD" in call for call in fail_calls)


def test_whitespace_only_treated_as_missing(monkeypatch):
    """Test that whitespace-only strings are treated as missing credentials."""
    monkeypatch.setenv("DB_HOST", "   ")
    monkeypatch.setenv("SCHEDULER_DB_PASSWORD", "   ")
    monkeypatch.setenv("WORKER_APP_PASSWORD", "   ")
    monkeypatch.setenv("WORKER_MIGRATOR_PASSWORD", "   ")

    monkeypatch.setattr(sys, "argv", ["kivoll-schedule"])

    with mock.patch("cliasi.cli.fail") as mock_fail:
        with pytest.raises(SystemExit) as exc_info:
            arguments.parse_schedule_args()

    assert exc_info.value.code == 1
    fail_calls = [call[0][0] for call in mock_fail.call_args_list]
    assert any("SCHEDULER_DB_PASSWORD" in call for call in fail_calls)
