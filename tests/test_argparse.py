import sys
from unittest import mock

import pytest

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
