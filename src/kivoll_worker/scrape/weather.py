"""
Weather module date generation.
"""

import logging
import sqlite3
from collections.abc import Sequence
from typing import Any, Literal

import openmeteo_requests
from cliasi import Cliasi
from openmeteo_requests import OpenMeteoRequestsError
from openmeteo_sdk.WeatherApiResponse import WeatherApiResponse

import kivoll_worker.storage

from ..common.config import config
from ..common.failure import log_error

cli: Cliasi = Cliasi("uninitialized")

Resolution = Literal["hourly", "daily", "current"]

# Module-level cache for valid columns, loaded from database on first access
_columns_cache: dict[Resolution, frozenset[str]] = {}


def _is_close(a: float, b: float) -> bool:
    return abs(a - b) < 1e-2 * 3


def weather() -> bool:
    """
    Fetch weather data and save it to database
    :return: Success status as boolean
    """
    global cli
    cli = Cliasi("weather")
    openmeteo = openmeteo_requests.Client()
    url: str
    parameters: dict[str, Any]
    locations: dict[str, dict[str, float | bool]]

    cli.log("Parsing configuration values")
    try:
        cfg_json = config()
        url = str(cfg_json["modules"]["weather"]["url"])
        parameters = dict(cfg_json["modules"]["weather"]["parameters"])
        locations = dict(cfg_json["modules"]["weather"]["locations"])
        if not (url and parameters):
            # If not both are valid (True) (not None)
            raise ValueError("url or parameters is malformed (not None or empty)")
    except (ValueError, TypeError) as e:
        cli.fail(
            f"Could not request weather data, configuration malformed ({e})\n"
            "Will skip gathering weather data",
            messages_stay_in_one_line=False,
        )
        log_error(e, "weather:config:read_request_parameters", False)
        return False

    cli.log("Validating requested weather parameters")
    # Validate requested parameters (lazily initializes cache from DB)
    hourly_params_raw = parameters.get("hourly", [])
    if not isinstance(hourly_params_raw, list):
        log_error(
            TypeError("hourly parameter is not a list"),
            "weather:config:invalid_parameter_type",
            False,
        )
        cli.warn("Hourly parameter is not a list", messages_stay_in_one_line=False)
        hourly_params_raw = [hourly_params_raw]
    hourly_params: list[str] = [str(p) for p in hourly_params_raw]

    daily_params_raw = parameters.get("daily", [])
    if not isinstance(daily_params_raw, list):
        log_error(
            TypeError("hourly parameter is not a list"),
            "weather:config:invalid_parameter_type",
            False,
        )
        cli.warn("Daily parameter is not a list", messages_stay_in_one_line=False)
        daily_params_raw = [daily_params_raw]
    daily_params: list[str] = [str(p) for p in daily_params_raw]

    current_params_raw = parameters.get("current", [])
    if not isinstance(current_params_raw, list):
        log_error(
            TypeError("hourly parameter is not a list"),
            "weather:config:invalid_parameter_type",
            False,
        )
        cli.warn("Current parameter is not a list", messages_stay_in_one_line=False)
        current_params_raw = [current_params_raw]
    current_params: list[str] = [str(p) for p in current_params_raw]

    valid_hourly, invalid_hourly = validate_parameters(hourly_params, "hourly")
    valid_daily, invalid_daily = validate_parameters(daily_params, "daily")
    valid_current, invalid_current = validate_parameters(current_params, "current")

    for inv in invalid_hourly:
        cli.warn(f"Invalid hourly parameter '{inv}' will be ignored")
        log_error(
            ValueError(f"Invalid hourly weather parameter requested: {inv}"),
            "weather:config:invalid_parameter",
            False,
        )
    for inv in invalid_daily:
        cli.warn(f"Invalid daily parameter '{inv}' will be ignored")
        log_error(
            ValueError(f"Invalid daily weather parameter requested: {inv}"),
            "weather:config:invalid_parameter",
            False,
        )
    for inv in invalid_current:
        cli.warn(f"Invalid current parameter '{inv}' will be ignored")
        log_error(
            ValueError(f"Invalid current weather parameter requested: {inv}"),
            "weather:config:invalid_parameter",
            False,
        )

    cli.log("Validation successful")

    # Update parameters to only include valid ones for the API request
    if valid_hourly:
        parameters["hourly"] = valid_hourly
    else:
        parameters.pop("hourly", None)
    if valid_daily:
        parameters["daily"] = valid_daily
    else:
        parameters.pop("daily", None)
    if valid_current:
        parameters["current"] = valid_current
    else:
        parameters.pop("current", None)

    # Parse locations
    enabled_locations = [
        (name, location)
        for name, location in locations.items()
        if location.get("enabled", False)
        and "latitude" in location
        and "longitude" in location
    ]

    parameters["latitude"] = [float(loc["latitude"]) for _, loc in enabled_locations]
    parameters["longitude"] = [float(loc["longitude"]) for _, loc in enabled_locations]

    task = cli.animate_message_download_non_blocking(
        f"Fetching weather at {url}", verbosity=logging.DEBUG
    )
    responses: list[WeatherApiResponse]
    try:
        responses = openmeteo.weather_api(url, parameters)
    except OpenMeteoRequestsError as e:
        task.stop()
        cli.fail(
            "Could not fetch weather data! (HTTPError)", messages_stay_in_one_line=False
        )
        log_error(e, "weather:config:request", False)
        return False

    task.stop()
    cli.success("Weather data fetched successfully!", verbosity=logging.DEBUG)

    cli.log("Writing to database")
    database = kivoll_worker.storage.connect()
    success = True
    saved = 0
    try:
        for response in responses:
            # Match response to location
            location_name = None
            for name, location in enabled_locations:
                if _is_close(response.Latitude(), location["latitude"]) and _is_close(
                    response.Longitude(), location["longitude"]
                ):
                    location_name = name
                    break

            if location_name is None:
                cli.warn(
                    f"Could not match response to location "
                    f"(lat={response.Latitude()}, lon={response.Longitude()})"
                )
                log_error(
                    ValueError(
                        f"Could not match weather response to location"
                        f" (lat={response.Latitude()}, lon={response.Longitude()})"
                    ),
                    "weather:dbstore:location_match",
                    False,
                )
                continue

            cli.log(f"Processing weather data for '{location_name}'")

            # Process current data
            if valid_current:
                current = response.Current()
                if not current:
                    log_error(
                        ValueError(
                            "current response is None even tough current requested"
                        ),
                        "weather:dbstore:current_none",
                        False,
                    )
                    cli.warn(
                        "Current weather data is None, even tough requested",
                        messages_stay_in_one_line=False,
                    )
                    continue
                current_timestamp = current.Time()
                current_values = [
                    var.Value()
                    for idx in range(len(valid_current))
                    if (var := current.Variables(idx)) is not None
                ]
                insert_weather_data(
                    database,
                    "current",
                    location_name,
                    [current_timestamp],
                    valid_current,
                    current_values,
                )
                cli.log(f"Inserted current weather data for {location_name}")

            # Process hourly data dynamically
            if valid_hourly:
                hourly = response.Hourly()
                if not hourly:
                    log_error(
                        ValueError(
                            "hourly response is None even tough hourly requested"
                        ),
                        "weather:dbstore:hourly_none",
                        False,
                    )
                    cli.warn(
                        "Hourly weather data is None, even tough requested",
                        messages_stay_in_one_line=False,
                    )
                    continue
                hourly_timestamps = list(
                    range(hourly.Time(), hourly.TimeEnd(), hourly.Interval())
                )
                hourly_arrays = [
                    var.ValuesAsNumpy()
                    for idx in range(len(valid_hourly))
                    if (var := hourly.Variables(idx)) is not None
                ]
                insert_weather_data(
                    database,
                    "hourly",
                    location_name,
                    hourly_timestamps,
                    valid_hourly,
                    hourly_arrays,
                )
                cli.log(
                    f"Inserted {len(hourly_timestamps)} hourly rows for {location_name}"
                )

            # Process daily data dynamically
            if valid_daily:
                daily = response.Daily()
                if not daily:
                    log_error(
                        ValueError(
                            "daily response is None even tough hourly requested"
                        ),
                        "weather:dbstore:daily_none",
                        False,
                    )
                    cli.warn(
                        "Daily weather data is None, even tough requested",
                        messages_stay_in_one_line=False,
                    )
                    continue
                daily_timestamps = list(
                    range(daily.Time(), daily.TimeEnd(), daily.Interval())
                )
                daily_arrays = [
                    var.ValuesAsNumpy()
                    for idx in range(len(valid_daily))
                    if (var := daily.Variables(idx)) is not None
                ]
                insert_weather_data(
                    database,
                    "daily",
                    location_name,
                    daily_timestamps,
                    valid_daily,
                    daily_arrays,
                )
                cli.log(
                    f"Inserted {len(daily_timestamps)} daily rows for {location_name}"
                )

            saved += 1

        if saved:
            cli.log("Committing changes")
            database.commit()
            cli.success("Weather data written to database", logging.DEBUG)
        else:
            cli.fail(
                "No weather data was saved to database! (no location match)",
                logging.DEBUG,
            )
            log_error(
                RuntimeError(
                    "No weather data was saved to database! (no location match)"
                ),
                "weather:dbstore:no_data_saved",
                False,
            )
            success = False
    except sqlite3.Error as e:
        success = False
        log_error(e, "weather:dbstore:sqlite", False)
        cli.fail(
            f"Could not store weather data to database!\nError: {e}",
            messages_stay_in_one_line=False,
        )
        database.rollback()
    except Exception as e:
        success = False
        log_error(e, "weather:dbstore:unknown", False)
        cli.fail(
            f"An unexpected error occurred while storing kletterzentrum data!\n"
            f"Error: {e}",
            messages_stay_in_one_line=False,
        )
        database.rollback()
    finally:
        database.close()

    return success


def _load_columns_from_db() -> None:
    """
    Load valid weather parameter columns from the database.
    Populates the module-level cache.
    """
    global _columns_cache

    conn = kivoll_worker.storage.connect()
    try:
        cursor = conn.execute("SELECT name, resolution FROM weather_parameters")
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        log_error(e, "weather:validate:cache:load_from_db", False)
        cli.fail(
            f"Could not load weather parameters from database: {e}",
            messages_stay_in_one_line=False,
        )
        raise
    finally:
        conn.close()

    hourly: set[str] = set()
    daily: set[str] = set()
    current: set[str] = set()

    for name, resolution in rows:
        match resolution:
            case "hourly":
                hourly.add(name)
            case "daily":
                daily.add(name)
            case "current":
                current.add(name)

    _columns_cache = {
        "hourly": frozenset(hourly),
        "daily": frozenset(daily),
        "current": frozenset(current),
    }


def get_valid_columns(resolution: Resolution) -> frozenset[str]:
    """
    Get the set of valid column names for a given resolution.
    Lazily loads from database on first access.

    :param resolution: One of 'hourly', 'daily', 'current'
    :return: frozenset of valid column names
    :raises ValueError: If resolution is unknown
    """
    if not _columns_cache:
        _load_columns_from_db()

    if resolution not in _columns_cache:
        e = ValueError(f"Unknown resolution: {resolution}")
        log_error(e, "weather:validate:unknown_resolution", False)
        raise e

    return _columns_cache[resolution]


def validate_parameters(
    requested: list[str],
    resolution: Resolution,
) -> tuple[list[str], list[str]]:
    """
    Validate requested parameters against valid columns for a resolution.

    :param requested: List of parameter names from config
    :param resolution: One of 'hourly', 'daily', 'current'
    :return: Tuple of (valid_parameters, invalid_parameters)
    """
    valid_cols = get_valid_columns(resolution)
    valid = [p for p in requested if p in valid_cols]
    invalid = [p for p in requested if p not in valid_cols]
    return valid, invalid


def insert_weather_data(
    conn: sqlite3.Connection,
    resolution: Resolution,
    location: str,
    timestamps: list[int],
    param_names: list[str],
    param_values: Sequence[Any],
) -> bool:
    """
    Insert weather data rows for a given resolution.

    :param conn: SQLite database connection
    :param resolution: One of 'hourly', 'daily', 'current'
    :param location: Location name
    :param timestamps: List of Unix timestamps
    :param param_names: List of parameter names (in order)
    :param param_values: List of values or numpy arrays (same order as param_names)
    :return: Success status as boolean
    """
    valid_columns = get_valid_columns(resolution)
    valid_indices = [i for i, name in enumerate(param_names) if name in valid_columns]
    valid_names = [param_names[i] for i in valid_indices]
    valid_arrays = [param_values[i] for i in valid_indices]

    if not valid_names:
        return False

    table = "weather_" + resolution
    columns = ["timestamp", "location"] + valid_names
    placeholders = ", ".join(["?"] * len(columns))
    sql = (
        f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    )

    for idx, ts in enumerate(timestamps):
        # Handle both single values (current) and arrays (hourly/daily)
        if resolution == "current":
            row_values = [
                float(val) if val is not None else None for val in valid_arrays
            ]
        else:
            row_values = [
                float(arr[idx]) if arr[idx] is not None else None
                for arr in valid_arrays
            ]
        try:
            conn.execute(sql, [ts, location] + row_values)
        except sqlite3.Error as e:
            log_error(e, "weather:dbstore:insert_row:" + resolution, False)
            cli.fail(
                f"Could not insert {resolution} weather data row for {location}"
                f" at {ts}!\nError: {e}",
                messages_stay_in_one_line=False,
            )
            return False
    return True
