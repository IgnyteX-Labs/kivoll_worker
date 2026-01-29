# Ensure core common modules provide the module-level globals used at import time
import pathlib

import openmeteo_requests
import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import kivoll_worker.common.config as _config_mod
import kivoll_worker.common.failure as _failure_mod


class _DummyErrors:
    def __init__(self):
        self.json = {"errors": [], "file": {"version": 1}}

    def save(self):
        return None

    def reload(self, *a, **k):
        return None

    def restore_default(self, *a, **k):
        self.json = {"errors": [], "file": {"version": 1}}


class _DummyConfig:
    def __init__(self):
        self.json = {
            "paths": {"data": str(pathlib.Path(".").resolve())},
            "file": {"version": 1},
        }

    def reload(self, *a, **k):
        return None

    def restore_default(self, *a, **k):
        self.json = {
            "paths": {"data": str(pathlib.Path(".").resolve())},
            "file": {"version": 1},
        }


# Apply minimal stand-ins if the real ones are not set yet
if not hasattr(_failure_mod, "_errors"):
    _failure_mod._errors = _DummyErrors()
# Patch out log_error at module level to avoid file operations during test import
_failure_mod.log_error = lambda *a, **k: None

if not hasattr(_config_mod, "_config"):
    _config_mod._config = _DummyConfig()
if not hasattr(_config_mod, "_data_dir"):
    _config_mod._data_dir = pathlib.Path(".")

# Now import the weather module (which expects the above globals)
from kivoll_worker.scrape import weather  # noqa: E402


def _create_weather_table(conn, resolution: str, columns: list[str]) -> None:
    cols_sql = ", ".join(f"{col} DOUBLE PRECISION" for col in columns)
    if resolution == "current":
        conn.execute(
            text(
                f"""
            DROP TABLE IF EXISTS weather_current;
            CREATE TABLE weather_current (
                fetched_at BIGINT NOT NULL,
                observed_at BIGINT NOT NULL,
                location TEXT NOT NULL,
                {cols_sql},
                PRIMARY KEY (fetched_at, location)
            );
            """
            )
        )
    elif resolution == "hourly":
        conn.execute(
            text(
                f"""
            DROP TABLE IF EXISTS weather_hourly;
            CREATE TABLE weather_hourly (
                forecast_time BIGINT NOT NULL,
                fetched_at BIGINT NOT NULL,
                location TEXT NOT NULL,
                {cols_sql},
                PRIMARY KEY (forecast_time, location, fetched_at)
            );
            """
            )
        )
    else:  # daily
        conn.execute(
            text(
                f"""
            DROP TABLE IF EXISTS weather_daily;
            CREATE TABLE weather_daily (
                forecast_date BIGINT NOT NULL,
                fetched_at BIGINT NOT NULL,
                location TEXT NOT NULL,
                {cols_sql},
                PRIMARY KEY (forecast_date, location, fetched_at)
            );
            """
            )
        )


# ---------------------
# Unit tests (fast)
# ---------------------


def test_is_close() -> None:
    assert weather._is_close(10.0, 10.01)
    assert not weather._is_close(10.0, 10.5)


def test_validate_parameters_with_cache() -> None:
    # Prepare a fake columns cache
    weather._columns_cache.clear()
    weather._columns_cache["hourly"] = frozenset({"t1", "t2"})

    valid, invalid = weather.validate_parameters(["t1", "bad"], "hourly", None)
    assert valid == ["t1"]
    assert invalid == ["bad"]


# ---------------------
# DB-backed tests
# ---------------------


@pytest.mark.database
def test_load_columns_from_db_and_get_valid_columns(db_engine, monkeypatch) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))

    # Create weather_parameters table and insert rows
    session.execute(
        text(
            "DROP TABLE IF EXISTS weather_parameters; CREATE TABLE weather_parameters (name TEXT, resolution TEXT);"
        )
    )
    session.execute(
        text(
            "INSERT INTO weather_parameters (name, resolution) VALUES ('temperature_2m', 'hourly'), ('precipitation_sum', 'daily'), ('wind_gusts_10m', 'current')"
        )
    )

    # Monkeypatch storage.connect to return a connection acquired from the session

    # Clear caches and load
    weather._columns_cache.clear()
    weather._table_cache.clear()

    # Use a short-lived connection for the DB access inside the function
    with session.connection() as conn:
        # monkeypatched storage.connect() will also return a connection; call loader
        weather._load_columns_from_db(conn)

    assert "temperature_2m" in weather.get_valid_columns("hourly", conn)
    assert "precipitation_sum" in weather.get_valid_columns("daily", conn)
    assert "wind_gusts_10m" in weather.get_valid_columns("current", conn)


@pytest.mark.database
def test_insert_daily_with_arrays(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    _create_weather_table(session, "daily", ["temperature_2m", "precipitation_sum"])

    weather._columns_cache.clear()
    weather._table_cache.clear()
    weather._columns_cache["daily"] = frozenset({"temperature_2m", "precipitation_sum"})

    with session.connection() as conn:
        ok = weather.insert_weather_data(
            conn,
            "daily",
            "loc",
            [100, 200],  # forecast_date values
            ["temperature_2m", "precipitation_sum"],
            [[5.0, 6.0], [0.1, 0.0]],
            fetched_at=1234,
        )
        assert ok

        rows = conn.execute(
            text(
                "SELECT forecast_date, fetched_at, location, temperature_2m, precipitation_sum FROM weather_daily ORDER BY forecast_date"
            )
        ).fetchall()
    assert rows == [(100, 1234, "loc", 5.0, 0.1), (200, 1234, "loc", 6.0, 0.0)]


@pytest.mark.database
def test_insert_returns_false_when_no_valid_params(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    _create_weather_table(session, "daily", ["temperature_2m"])

    weather._columns_cache.clear()
    weather._table_cache.clear()
    # Intentionally set cache to something else so provided names are invalid
    weather._columns_cache["daily"] = frozenset({"not_the_param"})

    with session.connection() as conn:
        ok = weather.insert_weather_data(
            conn,
            "daily",
            "loc",
            [1],
            ["temperature_2m"],
            [[10.0]],
            fetched_at=500,
        )
        assert not ok


# ---------------------
# Unsupported dialect test (unit)
# ---------------------


def test_insert_raises_on_unsupported_dialect(monkeypatch) -> None:
    class FakeDialect:
        name = "mysql"

    class FakeConn:
        def __init__(self):
            self.dialect = FakeDialect()

    # Ensure _get_weather_table is not called (it would require a real connection)
    monkeypatch.setattr(weather, "_get_weather_table", lambda conn, res: True)
    monkeypatch.setattr(weather, "log_error", lambda ex, context, fatal: None)

    weather._columns_cache.clear()
    weather._columns_cache["daily"] = frozenset({"temperature_2m"})

    fake_conn = FakeConn()

    with pytest.raises(weather.UnsupportedDialect):
        weather.insert_weather_data(
            fake_conn,
            "daily",
            "loc",
            [1],
            ["temperature_2m"],
            [[10.0]],
            fetched_at=1,
        )


# ---------------------
# Additional unit tests
# ---------------------


@pytest.fixture(autouse=True)
def _disable_log_error_and_init_minimal_config(monkeypatch, tmp_path):
    """Disable the real log_error and provide minimal config/errors globals used by modules.

    Some modules expect module-level variables like `_errors` (in common.failure)
    and `_config`/`_data_dir` (in common.config) to exist. Those are normally
    created by init routines at program start; tests should provide minimal
    stand-ins to avoid NameError and prevent touching disk.
    """
    # Patch the public log_error used by many modules to a no-op
    import kivoll_worker.common.config as config_mod
    import kivoll_worker.common.failure as failure_mod

    monkeypatch.setattr(failure_mod, "log_error", lambda *a, **k: None, raising=False)

    # Provide a minimal _errors object with required attributes
    class _DummyErrors:
        def __init__(self):
            self.json = {"errors": [], "file": {"version": 1}}

        def save(self):
            return None

        def reload(self, *a, **k):
            return None

        def restore_default(self, *a, **k):
            self.json = {"errors": [], "file": {"version": 1}}

    monkeypatch.setattr(failure_mod, "_errors", _DummyErrors(), raising=False)

    # Provide a minimal _config JSONFile-like object and data_dir
    class _DummyConfig:
        def __init__(self):
            self.json = {"paths": {"data": str(tmp_path)}, "file": {"version": 1}}

        def reload(self, *a, **k):
            return None

        def restore_default(self, *a, **k):
            self.json = {"paths": {"data": str(tmp_path)}, "file": {"version": 1}}

    monkeypatch.setattr(config_mod, "_config", _DummyConfig(), raising=False)
    monkeypatch.setattr(config_mod, "_data_dir", tmp_path, raising=False)

    # Also patch the weather module's imported log_error (in case it imported earlier)
    monkeypatch.setattr(weather, "log_error", lambda *a, **k: None, raising=False)

    yield


def test_raise_value_error_with_empty_url_or_parameters(monkeypatch) -> None:
    cfg = {"modules": {"weather": {"url": "", "parameters": {}, "locations": {}}}}
    monkeypatch.setattr(weather, "config", lambda: cfg)

    assert weather.weather(None) is False


def test_warn_on_nonlist_parameters(monkeypatch) -> None:
    cfg = {
        "modules": {
            "weather": {
                "url": "asd",
                "locations": {},
                "parameters": {
                    "hourly": "hourlyparam",
                    "daily": "dailyparam",
                    "current": "currentparam",
                },
            }
        }
    }

    captured_ex: set[str] = set({})

    def patched_logerror(ex: ValueError | TypeError, ctx, _fatal):
        nonlocal captured_ex
        assert isinstance(ex, ValueError) or isinstance(ex, TypeError)
        captured_ex.add(str(ex))

    monkeypatch.setattr(weather, "log_error", patched_logerror)
    monkeypatch.setattr(weather, "config", lambda: cfg)

    weather._columns_cache["hourly"] = frozenset({})
    weather._columns_cache["current"] = frozenset({})
    weather._columns_cache["daily"] = frozenset({})

    # Warnings should be issued for every one of the not valid params

    class _ShortCircuitEx(Exception):
        pass

    def end_on_anim_msg_nonblocking(*a, **k):
        raise _ShortCircuitEx()

    monkeypatch.setattr(
        weather.cli,
        "animate_message_download_non_blocking",
        end_on_anim_msg_nonblocking,
        raising=False,
    )
    from cliasi import Cliasi as cli_mod

    monkeypatch.setattr(
        cli_mod,
        "animate_message_download_non_blocking",
        end_on_anim_msg_nonblocking,
        raising=False,
    )

    with pytest.raises(_ShortCircuitEx):
        weather.weather(None)

    desired_ex = {
        "current parameter is not a list",
        "hourly parameter is not a list",
        "daily parameter is not a list",
        "Invalid hourly weather parameter requested: hourlyparam",
        "Invalid daily weather parameter requested: dailyparam",
        "Invalid current weather parameter requested: currentparam",
    }
    not_recieved = desired_ex - captured_ex
    too_much = captured_ex - desired_ex
    if not_recieved or too_much:
        pytest.fail(
            f"log output differs: too much: {too_much};not recieved: {not_recieved}"
        )


def test_get_valid_columns_unknown_resolution_raises(monkeypatch) -> None:
    weather._columns_cache.clear()
    weather._columns_cache["hourly"] = frozenset({"a"})
    with pytest.raises(ValueError):
        weather.get_valid_columns("bogus", None)


def test__load_columns_from_db_raises_on_sqlalchemy_error(monkeypatch) -> None:
    # Fake connection whose execute will raise SQLAlchemyError
    class BadConn:
        def execute(self, *a, **k):
            raise SQLAlchemyError("boom")

        def close(self):
            pass

    monkeypatch.setattr(weather, "log_error", lambda ex, context, fatal: None)
    weather._columns_cache.clear()

    with pytest.raises(SQLAlchemyError):
        weather._load_columns_from_db(BadConn())


# ---------------------
# DB-backed additional tests
# ---------------------


@pytest.mark.database
def test_get_weather_table_caches_table_object(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    _create_weather_table(session, "daily", ["t1"])  # creates weather_daily

    weather._table_cache.clear()
    with session.connection() as conn:
        t1 = weather._get_weather_table(conn, "daily")
        t2 = weather._get_weather_table(conn, "daily")
    assert t1 is t2


@pytest.mark.database
def test_insert_weather_data_returns_false_on_execute_error(
    db_engine, monkeypatch
) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    _create_weather_table(session, "daily", ["temperature_2m"])

    weather._columns_cache.clear()
    weather._table_cache.clear()
    weather._columns_cache["daily"] = frozenset({"temperature_2m"})

    # Use a short-lived connection and monkeypatch its execute to raise
    with session.connection() as conn:
        # (table reflection will be done on a managed connection below)

        def raise_execute(*a, **k):
            raise SQLAlchemyError("simulated execute failure")

        monkeypatch.setattr(conn, "execute", raise_execute)

        ok = weather.insert_weather_data(
            conn,
            "daily",
            "loc",
            [1],
            ["temperature_2m"],
            [[10.0]],
            fetched_at=1,
        )
        assert not ok


@pytest.mark.database
def test_insert_weather_data_handles_none_and_casting(db_engine) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
    _create_weather_table(session, "daily", ["temperature_2m", "precipitation_sum"])

    weather._columns_cache.clear()
    weather._table_cache.clear()
    weather._columns_cache["daily"] = frozenset({"temperature_2m", "precipitation_sum"})

    with session.connection() as conn:
        ok = weather.insert_weather_data(
            conn,
            "daily",
            "loc",
            [10, 20],
            ["temperature_2m", "precipitation_sum"],
            [[1.5, None], [0.0, 2.0]],
            fetched_at=111,
        )
        assert ok

        rows = conn.execute(
            text(
                "SELECT forecast_date, fetched_at, location, temperature_2m, precipitation_sum FROM weather_daily ORDER BY forecast_date"
            )
        ).fetchall()

    # second row should have NULL for temperature_2m (None in Python)
    assert rows[0] == (10, 111, "loc", 1.5, 0.0)
    assert rows[1] == (20, 111, "loc", None, 2.0)


# ---------------------
# Weather() flow tests (avoid asserting CLI)
# ---------------------


class _FakeVar:
    def __init__(self, values):
        self._values = values

    def Value(self):
        # scalar for Current
        return self._values

    def ValuesAsNumpy(self):
        # return list-like for Hourly/Daily
        return list(self._values)


class _FakeCurrent:
    def __init__(self, values, observed_at):
        self._vars = [_FakeVar(v) for v in values]
        self._time = observed_at

    def Time(self):
        return self._time

    def Variables(self, idx):
        if 0 <= idx < len(self._vars):
            return self._vars[idx]
        return None


class _FakeSeries:
    def __init__(self, values, start, end, interval):
        self._values = values
        self._start = start
        self._end = end
        self._interval = interval
        self._vars = [_FakeVar(v) for v in values]

    def Time(self):
        return self._start

    def TimeEnd(self):
        return self._end

    def Interval(self):
        return self._interval

    def Variables(self, idx):
        if 0 <= idx < len(self._vars):
            return self._vars[idx]
        return None


class _FakeResponse:
    def __init__(self, lat, lon, current=None, hourly=None, daily=None):
        self._lat = lat
        self._lon = lon
        self._current = current
        self._hourly = hourly
        self._daily = daily

    def Latitude(self):
        return self._lat

    def Longitude(self):
        return self._lon

    def Current(self):
        return self._current

    def Hourly(self):
        return self._hourly

    def Daily(self):
        return self._daily


@pytest.mark.database
def test_weather_success_inserts_all_resolutions(db_engine, monkeypatch):
    """End-to-end exercise of weather() writing current/hourly/daily rows."""
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))

    # Create tables
    _create_weather_table(session, "current", ["temperature_2m", "wind_gusts_10m"])
    _create_weather_table(session, "hourly", ["temperature_2m"])
    _create_weather_table(session, "daily", ["precipitation_sum"])

    # Prepare module caches to avoid _load_columns_from_db
    weather._columns_cache.clear()
    weather._columns_cache["current"] = frozenset({"temperature_2m", "wind_gusts_10m"})
    weather._columns_cache["hourly"] = frozenset({"temperature_2m"})
    weather._columns_cache["daily"] = frozenset({"precipitation_sum"})
    weather._table_cache.clear()

    # Fake config
    cfg = {
        "modules": {
            "weather": {
                "url": "http://example",
                "parameters": {
                    "current": ["temperature_2m", "wind_gusts_10m"],
                    "hourly": ["temperature_2m"],
                    "daily": ["precipitation_sum"],
                },
                "locations": {
                    "loc": {"enabled": True, "latitude": 48.0, "longitude": 11.0}
                },
            }
        }
    }

    monkeypatch.setattr(weather, "_columns_cache", weather._columns_cache)

    # Build a fake response that matches the location
    # Current: two scalar vars
    current = _FakeCurrent([3.3, 1.2], observed_at=999)
    # Hourly: one variable array for two timestamps
    hourly = _FakeSeries([[10.0, 11.0]], start=1000, end=1002, interval=1)
    # Daily: one variable array for two timestamps
    daily = _FakeSeries([[0.5, 0.0]], start=2000, end=2002, interval=1)

    resp = _FakeResponse(48.0, 11.0, current=current, hourly=hourly, daily=daily)

    # Monkeypatch the API client to return our response
    def fake_api(url, params):
        return [resp]

    monkeypatch.setattr(
        openmeteo_requests.Client,
        "weather_api",
        lambda self, url, params: fake_api(url, params),
    )

    # Monkeypatch config() to return our cfg
    monkeypatch.setattr(weather, "config", lambda: cfg)

    with session.connection() as conn:
        ok = weather.weather(conn)
        assert ok is True

        # Verify some rows in DB
        cur_rows = conn.execute(
            text(
                "SELECT fetched_at, observed_at, location, temperature_2m, wind_gusts_10m FROM weather_current"
            )
        ).fetchall()
        assert cur_rows and cur_rows[0][2] == "loc"

        hourly_rows = conn.execute(
            text(
                "SELECT forecast_time, fetched_at, location, temperature_2m FROM weather_hourly ORDER BY forecast_time"
            )
        ).fetchall()
        assert hourly_rows and hourly_rows[0][0] == 1000

        daily_rows = conn.execute(
            text(
                "SELECT forecast_date, fetched_at, location, precipitation_sum FROM weather_daily ORDER BY forecast_date"
            )
        ).fetchall()
        assert daily_rows and daily_rows[0][0] == 2000


@pytest.mark.database
def test_weather_handles_missing_subobjects_and_returns_false(
    db_engine, monkeypatch
) -> None:
    session = db_engine
    session.execute(text("CREATE SCHEMA IF NOT EXISTS public"))

    # setup config with parameters for each resolution
    cfg = {
        "modules": {
            "weather": {
                "url": "http://example",
                "parameters": {
                    "current": ["temperature_2m"],
                    "hourly": ["temperature_2m"],
                    "daily": ["precipitation_sum"],
                },
                "locations": {
                    "loc": {"enabled": True, "latitude": 48.0, "longitude": 11.0}
                },
            }
        }
    }

    # set caches and avoid CLI interactions
    weather._columns_cache.clear()
    weather._columns_cache["current"] = frozenset({"temperature_2m"})
    weather._columns_cache["hourly"] = frozenset({"temperature_2m"})
    weather._columns_cache["daily"] = frozenset({"precipitation_sum"})
    weather._table_cache.clear()

    monkeypatch.setattr(weather, "config", lambda: cfg)

    # Response where Current/Hourly/Daily return None despite being requested
    resp = _FakeResponse(48.0, 11.0, current=None, hourly=None, daily=None)
    monkeypatch.setattr(
        openmeteo_requests.Client, "weather_api", lambda self, url, params: [resp]
    )

    with session.connection() as conn:
        ok = weather.weather(conn)
    assert ok is False


@pytest.mark.database
def test_weather_malformed_config_returns_false(monkeypatch) -> None:
    # Malformed config where url or parameters are falsy
    cfg = {"modules": {"weather": {"url": None, "parameters": None, "locations": {}}}}
    monkeypatch.setattr(weather, "config", lambda: cfg)

    result = weather.weather(None)
    assert result is False


@pytest.mark.database
def test_weather_request_error_returns_false(monkeypatch) -> None:
    # Valid-ish config but API client raises
    cfg = {
        "modules": {
            "weather": {
                "url": "http://example",
                "parameters": {"hourly": ["temperature_2m"]},
                "locations": {
                    "loc": {"enabled": True, "latitude": 48.0, "longitude": 11.0}
                },
            }
        }
    }
    monkeypatch.setattr(weather, "config", lambda: cfg)
    # Ensure column cache contains hourly parameter
    weather._columns_cache.clear()
    weather._columns_cache["hourly"] = frozenset({"temperature_2m"})

    # API raises request error
    def raise_request(*a, **k):
        raise openmeteo_requests.OpenMeteoRequestsError("http fail")

    monkeypatch.setattr(
        openmeteo_requests.Client,
        "weather_api",
        lambda self, url, params: (_ for _ in ()).throw(
            openmeteo_requests.OpenMeteoRequestsError("http fail")
        ),
    )

    result = weather.weather(None)
    assert result is False
