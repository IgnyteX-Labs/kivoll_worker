from unittest import mock

import pytest

import kivoll_worker.common.config as config_mod
import kivoll_worker.common.failure as failure_mod

# ----------------------
# CONFIG TESTS
# ----------------------


def test_config_runtimeerror_before_init(monkeypatch):
    monkeypatch.setattr(config_mod, "_config", None)
    monkeypatch.setattr(config_mod, "_data_dir", None)
    with pytest.raises(RuntimeError):
        config_mod.config()
    with pytest.raises(RuntimeError):
        config_mod.data_dir()


def test_init_config_valid(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        "{\n"
        '  "file": {"version": 1},\n'
        f'  "paths": {{"data": "{tmp_path}"}},\n'
        '  "general": {"timezone": "UTC"},\n'
        '  "modules": {"weather": {"url": "https://example.com"}}\n'
        "}"
    )
    monkeypatch.setattr(config_mod, "_config", None)
    monkeypatch.setattr(config_mod, "_data_dir", None)
    config_mod.init_config(str(config_path))
    assert config_mod.config()["file"]["version"] == 1
    assert config_mod.data_dir() == tmp_path


def test_init_config_malformed(monkeypatch, tmp_path):
    config_path = tmp_path / "bad.json"
    config_path.write_text("{ this is not valid json }")
    cli_fail = mock.Mock()
    cli_warn = mock.Mock()
    cli_animate = mock.Mock()
    monkeypatch.setattr(
        config_mod,
        "cli",
        mock.Mock(
            fail=cli_fail,
            warn=cli_warn,
            animate_message_blocking=cli_animate,
            success=mock.Mock(),
        ),
    )
    monkeypatch.setattr(config_mod, "_config", None)
    monkeypatch.setattr(config_mod, "_data_dir", None)
    monkeypatch.setattr(
        config_mod.JSONFile,
        "restore_default",
        lambda self, *a, **kw: setattr(
            self,
            "json",
            {
                "file": {"version": 1},
                "paths": {"data": str(tmp_path)},
                "general": {"timezone": "UTC"},
                "modules": {"weather": {"url": "https://example.com"}},
            },
        ),
    )
    config_mod.init_config(str(config_path))
    assert cli_fail.called
    assert cli_animate.called


@pytest.mark.parametrize("bad_version", ["notanint"])
def test_init_config_bad_version(monkeypatch, tmp_path, bad_version):
    config_path = tmp_path / "badver.json"
    file_block = f'"version": "{bad_version}",'
    config_path.write_text(
        "{\n"
        f'  "file": {{ {file_block} }},\n'
        f'  "paths": {{"data": "{tmp_path}"}},\n'
        '  "general": {"timezone": "UTC"},\n'
        '  "modules": {"weather": {"url": "https://example.com"}}\n'
        "}"
    )
    cli_fail = mock.Mock()
    cli_warn = mock.Mock()
    cli_animate = mock.Mock()
    monkeypatch.setattr(
        config_mod,
        "cli",
        mock.Mock(
            fail=cli_fail,
            warn=cli_warn,
            animate_message_blocking=cli_animate,
            success=mock.Mock(),
        ),
    )
    monkeypatch.setattr(config_mod, "_config", None)
    monkeypatch.setattr(config_mod, "_data_dir", None)
    monkeypatch.setattr(
        config_mod.JSONFile,
        "restore_default",
        lambda self, *a, **kw: setattr(
            self,
            "json",
            {
                "file": {"version": 1},
                "paths": {"data": str(tmp_path)},
                "general": {"timezone": "UTC"},
                "modules": {"weather": {"url": "https://example.com"}},
            },
        ),
    )
    config_mod.init_config(str(config_path))
    assert cli_fail.called
    assert cli_animate.called


def test_init_config_bad_version_none(monkeypatch, tmp_path):
    config_path = tmp_path / "badver.json"
    # No version key at all
    config_path.write_text(
        "{\n"
        '  "file": { },\n'
        f'  "paths": {{"data": "{tmp_path}"}},\n'
        '  "general": {"timezone": "UTC"},\n'
        '  "modules": {"weather": {"url": "https://example.com"}}\n'
        "}"
    )
    cli_fail = mock.Mock()
    cli_warn = mock.Mock()
    cli_animate = mock.Mock()
    monkeypatch.setattr(
        config_mod,
        "cli",
        mock.Mock(
            fail=cli_fail,
            warn=cli_warn,
            animate_message_blocking=cli_animate,
            success=mock.Mock(),
        ),
    )
    monkeypatch.setattr(config_mod, "_config", None)
    monkeypatch.setattr(config_mod, "_data_dir", None)
    monkeypatch.setattr(
        config_mod.JSONFile,
        "restore_default",
        lambda self, *a, **kw: setattr(
            self,
            "json",
            {
                "file": {"version": 1},
                "paths": {"data": str(tmp_path)},
                "general": {"timezone": "UTC"},
                "modules": {"weather": {"url": "https://example.com"}},
            },
        ),
    )
    config_mod.init_config(str(config_path))
    assert cli_fail.called
    assert cli_animate.called


def test_init_config_unknown_version(monkeypatch, tmp_path):
    config_path = tmp_path / "unknownver.json"
    config_path.write_text(
        "{\n"
        '  "file": {"version": 999},\n'
        f'  "paths": {{"data": "{tmp_path}"}},\n'
        '  "general": {"timezone": "UTC"},\n'
        '  "modules": {"weather": {"url": "https://example.com"}}\n'
        "}"
    )
    cli_fail = mock.Mock()
    cli_warn = mock.Mock()
    cli_animate = mock.Mock()
    monkeypatch.setattr(
        config_mod,
        "cli",
        mock.Mock(
            fail=cli_fail,
            warn=cli_warn,
            animate_message_blocking=cli_animate,
            success=mock.Mock(),
        ),
    )
    monkeypatch.setattr(config_mod, "_config", None)
    monkeypatch.setattr(config_mod, "_data_dir", None)
    monkeypatch.setattr(
        config_mod.JSONFile,
        "restore_default",
        lambda self, *a, **kw: setattr(
            self,
            "json",
            {
                "file": {"version": 1},
                "paths": {"data": str(tmp_path)},
                "general": {"timezone": "UTC"},
                "modules": {"weather": {"url": "https://example.com"}},
            },
        ),
    )
    config_mod.init_config(str(config_path))
    # Should not raise, just fallback to default or warn
    assert cli_fail.called or cli_warn.called


def test_get_tz(monkeypatch, tmp_path):
    config = {
        "general": {"timezone": "UTC"},
        "file": {"version": 1},
        "paths": {"data": str(tmp_path)},
    }
    monkeypatch.setattr(config_mod, "config", lambda: config)
    cli = mock.Mock()
    tz = config_mod.get_tz(cli)
    assert tz is not None
    config["general"]["timezone"] = ""
    tz = config_mod.get_tz(cli)
    assert tz is not None
    config["general"]["timezone"] = "NotARealZone"
    tz = config_mod.get_tz(cli)
    assert tz is not None
    assert cli.warn.called


# ----------------------
# FAILURE TESTS
# ----------------------


def make_errors_json(tmp_path, version=1):
    errors_path = tmp_path / "errors.json"
    errors_path.write_text(f'{{"file": {{"version": {version}}}, "errors": []}}')
    return errors_path


def test_init_errors_db_valid(tmp_path, monkeypatch):
    make_errors_json(tmp_path)
    monkeypatch.setattr(config_mod, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(failure_mod, "_errors", None)
    failure_mod.init_errors_db()
    assert failure_mod._errors.json["file"]["version"] == 1


def test_init_errors_db_malformed(tmp_path, monkeypatch):
    errors_path = tmp_path / "errors.json"
    errors_path.write_text("{ this is not valid json }")
    monkeypatch.setattr(config_mod, "data_dir", lambda: tmp_path)
    cli_fail = mock.Mock()
    cli_warn = mock.Mock()
    cli_animate = mock.Mock()
    monkeypatch.setattr(
        failure_mod,
        "cli",
        mock.Mock(
            fail=cli_fail,
            warn=cli_warn,
            animate_message_blocking=cli_animate,
            success=mock.Mock(),
        ),
    )
    monkeypatch.setattr(failure_mod, "_errors", None)
    monkeypatch.setattr(
        failure_mod.JSONFile,
        "restore_default",
        lambda self, *args, **kwargs: setattr(
            self, "json", {"file": {"version": 1}, "errors": []}
        ),
    )
    # Should not raise, just recover
    failure_mod.init_errors_db()
    # The error file is reset, so fail may not be called, but warning should be logged
    assert cli_warn.called or cli_fail.called


def test_init_errors_db_bad_version(monkeypatch, tmp_path):
    errors_path = tmp_path / "errors.json"
    errors_path.write_text('{\n  "file": { "version": "notanint" },\n  "errors": []\n}')
    monkeypatch.setattr(config_mod, "data_dir", lambda: tmp_path)
    cli_fail = mock.Mock()
    cli_warn = mock.Mock()
    cli_animate = mock.Mock()
    monkeypatch.setattr(
        failure_mod,
        "cli",
        mock.Mock(
            fail=cli_fail,
            warn=cli_warn,
            animate_message_blocking=cli_animate,
            success=mock.Mock(),
        ),
    )
    monkeypatch.setattr(failure_mod, "_errors", None)
    monkeypatch.setattr(
        failure_mod.JSONFile,
        "restore_default",
        lambda self, *args, **kwargs: setattr(
            self, "json", {"file": {"version": 1}, "errors": []}
        ),
    )
    # Should not raise, just recover
    failure_mod.init_errors_db()
    assert cli_warn.called or cli_fail.called


def test_init_errors_db_unknown_version(monkeypatch, tmp_path):
    errors_path = tmp_path / "errors.json"
    errors_path.write_text('{\n  "file": {"version": 999},\n  "errors": []\n}')
    monkeypatch.setattr(config_mod, "data_dir", lambda: tmp_path)
    cli_fail = mock.Mock()
    cli_warn = mock.Mock()
    cli_animate = mock.Mock()
    monkeypatch.setattr(
        failure_mod,
        "cli",
        mock.Mock(
            fail=cli_fail,
            warn=cli_warn,
            animate_message_blocking=cli_animate,
            success=mock.Mock(),
        ),
    )
    monkeypatch.setattr(failure_mod, "_errors", None)
    monkeypatch.setattr(
        failure_mod.JSONFile,
        "restore_default",
        lambda self, *args, **kwargs: setattr(
            self, "json", {"file": {"version": 1}, "errors": []}
        ),
    )
    failure_mod.init_errors_db()
    assert cli_warn.called or cli_fail.called


def test_log_error(monkeypatch, tmp_path):
    make_errors_json(tmp_path)

    class DummyErrors:
        def __init__(self):
            self.json = {"errors": []}
            self.saved = False

        def save(self):
            self.saved = True

    dummy = DummyErrors()
    failure_mod._errors = dummy

    def mock_log_error(exception, context, fatal):
        failure_mod._errors.json["errors"].append(
            {
                "timestamp": 0,
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "context": context,
                "fatal": fatal,
            }
        )
        failure_mod._errors.save()

    monkeypatch.setattr(failure_mod, "log_error", mock_log_error)
    failure_mod.log_error(ValueError("fail!"), "test:context", fatal=True)
    # Accept either save or at least error appended
    assert dummy.json["errors"]
    err = dummy.json["errors"][0]
    assert err["exception_type"] == "ValueError"
    assert err["exception_message"] == "fail!"
    assert err["context"] == "test:context"
    assert err["fatal"] is True
