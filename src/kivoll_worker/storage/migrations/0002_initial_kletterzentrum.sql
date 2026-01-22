-- 0002_initial_kletterzentrum.sql
-- Create kletterzentrum data table


CREATE TABLE IF NOT EXISTS kletterzentrum_data
(
    fetched_at
        INTEGER
        PRIMARY
            KEY,
    overall
        INTEGER,
    seil
        INTEGER,
    boulder
        INTEGER,
    open_sectors
        INTEGER,
    total_sectors
        INTEGER
);