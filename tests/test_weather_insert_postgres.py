import os

import pytest
from sqlalchemy import create_engine

from kivoll_worker.scrape import weather


def _create_weather_table(conn, resolution: str, columns: list[str]) -> None:
    cols_sql = ", ".join(f"{col} DOUBLE PRECISION" for col in columns)
    conn.exec_driver_sql(
        f"""
        DROP TABLE IF EXISTS weather_{resolution};
        CREATE TABLE weather_{resolution} (
            timestamp BIGINT NOT NULL,
            location TEXT NOT NULL,
            {cols_sql},
            PRIMARY KEY (timestamp, location)
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

        conn.rollback()
