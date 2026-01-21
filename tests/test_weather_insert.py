from sqlalchemy import create_engine

from kivoll_worker.scrape import weather


def _create_weather_table(conn, resolution: str, columns: list[str]) -> None:
    cols_sql = ", ".join(f"{col} REAL" for col in columns)
    conn.exec_driver_sql(
        f"""
        CREATE TABLE weather_{resolution} (
            timestamp INTEGER NOT NULL,
            location TEXT NOT NULL,
            {cols_sql},
            PRIMARY KEY (timestamp, location)
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
            [1, 2],
            ["temperature_2m"],
            [[10.5, 11.5]],
        )
        assert ok

        rows = conn.exec_driver_sql(
            "SELECT timestamp, location, temperature_2m "
            "FROM weather_hourly ORDER BY timestamp"
        ).fetchall()
        assert rows == [(1, "loc", 10.5), (2, "loc", 11.5)]

        ok = weather.insert_weather_data(
            conn,
            "hourly",
            "loc",
            [1],
            ["temperature_2m"],
            [[20.0]],
        )
        assert ok

        updated = conn.exec_driver_sql(
            "SELECT temperature_2m FROM weather_hourly "
            "WHERE timestamp = 1 AND location = 'loc'"
        ).scalar_one()
        assert updated == 20.0


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
            [100],
            ["temperature_2m", "wind_gusts_10m"],
            [1.0, 5.0],
        )
        assert ok

        row = conn.exec_driver_sql(
            "SELECT timestamp, location, temperature_2m, wind_gusts_10m "
            "FROM weather_current"
        ).fetchone()
        assert row == (100, "spot", 1.0, 5.0)
