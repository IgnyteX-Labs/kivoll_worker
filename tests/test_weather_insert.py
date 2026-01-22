from sqlalchemy import create_engine

from kivoll_worker.scrape import weather


def _create_weather_table(conn, resolution: str, columns: list[str]) -> None:
    cols_sql = ", ".join(f"{col} REAL" for col in columns)
    if resolution == "current":
        conn.exec_driver_sql(
            f"""
            CREATE TABLE weather_current (
                fetched_at INTEGER NOT NULL,
                observed_at INTEGER NOT NULL,
                location TEXT NOT NULL,
                {cols_sql},
                PRIMARY KEY (fetched_at, location)
            )
            """
        )
    elif resolution == "hourly":
        conn.exec_driver_sql(
            f"""
            CREATE TABLE weather_hourly (
                forecast_time INTEGER NOT NULL,
                fetched_at INTEGER NOT NULL,
                location TEXT NOT NULL,
                {cols_sql},
                PRIMARY KEY (forecast_time, location, fetched_at)
            )
            """
        )
    else:  # daily
        conn.exec_driver_sql(
            f"""
            CREATE TABLE weather_daily (
                forecast_date INTEGER NOT NULL,
                fetched_at INTEGER NOT NULL,
                location TEXT NOT NULL,
                {cols_sql},
                PRIMARY KEY (forecast_date, location, fetched_at)
            )
            """
        )


def test_insert_hourly_upserts_latest_value() -> None:
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        _create_weather_table(conn, "hourly", ["temperature_2m"])
        weather._columns_cache.clear()
        weather._table_cache.clear()
        weather._columns_cache["hourly"] = frozenset({"temperature_2m"})

        ok = weather.insert_weather_data(
            conn,
            "hourly",
            "loc",
            [1, 2],  # forecast_time values
            ["temperature_2m"],
            [[10.5, 11.5]],
            fetched_at=1000,
        )
        assert ok

        rows = conn.exec_driver_sql(
            "SELECT forecast_time, fetched_at, location, temperature_2m "
            "FROM weather_hourly ORDER BY forecast_time"
        ).fetchall()
        assert rows == [(1, 1000, "loc", 10.5), (2, 1000, "loc", 11.5)]

        # Insert same forecast_time with different fetched_at - should create new rows
        ok = weather.insert_weather_data(
            conn,
            "hourly",
            "loc",
            [1],
            ["temperature_2m"],
            [[20.0]],
            fetched_at=2000,  # Different fetch time
        )
        assert ok

        # Now we should have 3 rows (2 original + 1 new forecast snapshot)
        all_rows = conn.exec_driver_sql(
            "SELECT forecast_time, fetched_at, temperature_2m FROM weather_hourly "
            "WHERE location = 'loc' ORDER BY forecast_time, fetched_at"
        ).fetchall()
        assert len(all_rows) == 3
        assert all_rows[0] == (1, 1000, 10.5)  # Original
        assert all_rows[1] == (1, 2000, 20.0)  # New snapshot
        assert all_rows[2] == (2, 1000, 11.5)  # Original


def test_insert_current_accepts_scalar_values() -> None:
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        _create_weather_table(conn, "current", ["temperature_2m", "wind_gusts_10m"])
        weather._columns_cache.clear()
        weather._table_cache.clear()
        weather._columns_cache["current"] = frozenset(
            {"temperature_2m", "wind_gusts_10m"}
        )

        ok = weather.insert_weather_data(
            conn,
            "current",
            "spot",
            [100],  # This is now the fetched_at list (one item for current)
            ["temperature_2m", "wind_gusts_10m"],
            [1.0, 5.0],
            fetched_at=100,
            observed_at=90,  # API's observation time
        )
        assert ok

        row = conn.exec_driver_sql(
            "SELECT fetched_at, observed_at, location, temperature_2m, wind_gusts_10m "
            "FROM weather_current"
        ).fetchone()
        assert row == (100, 90, "spot", 1.0, 5.0)
