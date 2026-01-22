import os

import pytest
from sqlalchemy import create_engine

from kivoll_worker.scrape import weather


def _create_weather_table(conn, resolution: str, columns: list[str]) -> None:
    cols_sql = ", ".join(f"{col} DOUBLE PRECISION" for col in columns)
    if resolution == "current":
        conn.exec_driver_sql(
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
    elif resolution == "hourly":
        conn.exec_driver_sql(
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
    else:  # daily
        conn.exec_driver_sql(
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


@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_URL"),
    reason="Set TEST_POSTGRES_URL (e.g. postgresql+psycopg://postgres:postgres@localhost:5433/postgres)",
)
def test_insert_hourly_upserts_latest_value_postgres() -> None:
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    with engine.connect() as conn:
        conn.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS public")
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
            fetched_at=2000,
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

        conn.rollback()
