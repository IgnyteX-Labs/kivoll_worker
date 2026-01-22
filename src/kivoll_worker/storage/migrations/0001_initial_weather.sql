-- 0001_initial_weather.sql
-- Create initial weather tables

-- =========================
-- HOURLY WEATHER DATA TABLE
-- =========================
-- Each row represents a forecasted hour captured at a specific fetch time.
-- forecast_time: the hour being forecasted (from API)
-- fetched_at: when we fetched this forecast (allows tracking forecast evolution)

CREATE TABLE IF NOT EXISTS weather_hourly
(
    forecast_time              INTEGER NOT NULL,
    fetched_at                 INTEGER NOT NULL,
    location                   TEXT    NOT NULL,
    -- Temperature & Humidity
    temperature_2m             REAL,
    relative_humidity_2m       REAL,
    dewpoint_2m                REAL,
    apparent_temperature       REAL,
    -- Precipitation
    precipitation_probability  REAL,
    precipitation              REAL,
    rain                       REAL,
    showers                    REAL,
    snowfall                   REAL,
    snow_depth                 REAL,
    -- Conditions
    weathercode                REAL,
    pressure_msl               REAL,
    surface_pressure           REAL,
    cloud_cover                REAL,
    cloud_cover_low            REAL,
    cloud_cover_mid            REAL,
    cloud_cover_high           REAL,
    visibility                 REAL,
    evapotranspiration         REAL,
    et0_fao_evapotranspiration REAL,
    vapour_pressure_deficit    REAL,
    -- Wind at various heights
    wind_speed_10m             REAL,
    wind_speed_80m             REAL,
    wind_speed_120m            REAL,
    wind_speed_180m            REAL,
    wind_direction_10m         REAL,
    wind_direction_80m         REAL,
    wind_direction_120m        REAL,
    wind_direction_180m        REAL,
    wind_gusts_10m             REAL,
    -- Temperature at various heights
    temperature_80m            REAL,
    temperature_120m           REAL,
    temperature_180m           REAL,
    -- Soil temperature
    soil_temperature_0cm       REAL,
    soil_temperature_6cm       REAL,
    soil_temperature_18cm      REAL,
    soil_temperature_54cm      REAL,
    -- Soil moisture
    soil_moisture_0_1cm        REAL,
    soil_moisture_1_3cm        REAL,
    soil_moisture_3_9cm        REAL,
    soil_moisture_9_27cm       REAL,
    soil_moisture_27_81cm      REAL,
    PRIMARY KEY (forecast_time, location, fetched_at)
);

CREATE INDEX IF NOT EXISTS idx_weather_hourly_location ON weather_hourly (location);
CREATE INDEX IF NOT EXISTS idx_weather_hourly_forecast_time ON weather_hourly (forecast_time);
CREATE INDEX IF NOT EXISTS idx_weather_hourly_fetched_at ON weather_hourly (fetched_at);

-- =========================
-- DAILY WEATHER DATA TABLE
-- =========================
-- Each row represents a forecasted day captured at a specific fetch time.
-- forecast_date: the day being forecasted (from API, Unix timestamp at midnight)
-- fetched_at: when we fetched this forecast (allows tracking forecast evolution)

CREATE TABLE IF NOT EXISTS weather_daily
(
    forecast_date                 INTEGER NOT NULL,
    fetched_at                    INTEGER NOT NULL,
    location                      TEXT    NOT NULL,
    -- Conditions
    weathercode                   REAL,
    -- Temperature
    temperature_2m_max            REAL,
    temperature_2m_min            REAL,
    apparent_temperature_max      REAL,
    apparent_temperature_min      REAL,
    -- Sun
    sunrise                       INTEGER,
    sunset                        INTEGER,
    daylight_duration             REAL,
    sunshine_duration             REAL,
    uv_index_max                  REAL,
    uv_index_clear_sky_max        REAL,
    -- Precipitation
    rain_sum                      REAL,
    showers_sum                   REAL,
    snowfall_sum                  REAL,
    precipitation_sum             REAL,
    precipitation_hours           REAL,
    precipitation_probability_max REAL,
    -- Wind
    wind_speed_10m_max            REAL,
    wind_gusts_10m_max            REAL,
    wind_direction_10m_dominant   REAL,
    -- Radiation
    shortwave_radiation_sum       REAL,
    et0_fao_evapotranspiration    REAL,
    PRIMARY KEY (forecast_date, location, fetched_at)
);

CREATE INDEX IF NOT EXISTS idx_weather_daily_location ON weather_daily (location);
CREATE INDEX IF NOT EXISTS idx_weather_daily_forecast_date ON weather_daily (forecast_date);
CREATE INDEX IF NOT EXISTS idx_weather_daily_fetched_at ON weather_daily (fetched_at);

-- =========================
-- CURRENT WEATHER DATA TABLE
-- =========================
-- Each row represents a current weather observation captured at fetch time.
-- fetched_at: when we fetched this data (unique per fetch)
-- observed_at: when the API says this observation was made (updates every ~15 min)

CREATE TABLE IF NOT EXISTS weather_current
(
    fetched_at           INTEGER NOT NULL,
    observed_at          INTEGER NOT NULL,
    location             TEXT    NOT NULL,
    temperature_2m       REAL,
    relative_humidity_2m REAL,
    apparent_temperature REAL,
    is_day               REAL,
    precipitation        REAL,
    rain                 REAL,
    showers              REAL,
    snowfall             REAL,
    weathercode          REAL,
    cloud_cover          REAL,
    pressure_msl         REAL,
    surface_pressure     REAL,
    wind_speed_10m       REAL,
    wind_direction_10m   REAL,
    wind_gusts_10m       REAL,
    PRIMARY KEY (fetched_at, location)
);

CREATE INDEX IF NOT EXISTS idx_weather_current_location ON weather_current (location);
CREATE INDEX IF NOT EXISTS idx_weather_current_fetched_at ON weather_current (fetched_at);
CREATE INDEX IF NOT EXISTS idx_weather_current_observed_at ON weather_current (observed_at);


-- =========================
-- static weather parameters table (compatible parameters list)
-- =========================

CREATE TABLE IF NOT EXISTS weather_parameters
(
    name        TEXT NOT NULL,
    resolution  TEXT NOT NULL CHECK (resolution IN ('hourly', 'daily', 'current')),
    unit        TEXT,
    description TEXT,
    PRIMARY KEY (name, resolution)
);

-- =========================
-- HOURLY WEATHER PARAMETERS
-- =========================

INSERT INTO weather_parameters (name, resolution, unit, description)
VALUES ('temperature_2m', 'hourly', '°C', 'Air temperature at 2 meters above ground'),
       ('relative_humidity_2m', 'hourly', '%', 'Relative humidity at 2 meters'),
       ('dewpoint_2m', 'hourly', '°C', 'Dew point temperature at 2 meters'),
       ('apparent_temperature', 'hourly', '°C', 'Perceived temperature'),
       ('precipitation_probability', 'hourly', '%', 'Probability of precipitation'),
       ('precipitation', 'hourly', 'mm', 'Total precipitation (rain, showers, snow)'),
       ('rain', 'hourly', 'mm', 'Rainfall amount'),
       ('showers', 'hourly', 'mm', 'Showers amount'),
       ('snowfall', 'hourly', 'cm', 'Snowfall amount'),
       ('snow_depth', 'hourly', 'm', 'Snow depth'),
       ('weathercode', 'hourly', NULL, 'Weather condition code'),
       ('pressure_msl', 'hourly', 'hPa', 'Mean sea level pressure'),
       ('surface_pressure', 'hourly', 'hPa', 'Surface air pressure'),
       ('cloud_cover', 'hourly', '%', 'Total cloud cover'),
       ('cloud_cover_low', 'hourly', '%', 'Low-level cloud cover'),
       ('cloud_cover_mid', 'hourly', '%', 'Mid-level cloud cover'),
       ('cloud_cover_high', 'hourly', '%', 'High-level cloud cover'),
       ('visibility', 'hourly', 'm', 'Horizontal visibility'),
       ('evapotranspiration', 'hourly', 'mm', 'Evapotranspiration'),
       ('et0_fao_evapotranspiration', 'hourly', 'mm',
        'Reference evapotranspiration (ET₀)'),
       ('vapour_pressure_deficit', 'hourly', 'kPa', 'Vapour pressure deficit'),

       ('wind_speed_10m', 'hourly', 'km/h', 'Wind speed at 10 meters'),
       ('wind_speed_80m', 'hourly', 'km/h', 'Wind speed at 80 meters'),
       ('wind_speed_120m', 'hourly', 'km/h', 'Wind speed at 120 meters'),
       ('wind_speed_180m', 'hourly', 'km/h', 'Wind speed at 180 meters'),

       ('wind_direction_10m', 'hourly', '°', 'Wind direction at 10 meters'),
       ('wind_direction_80m', 'hourly', '°', 'Wind direction at 80 meters'),
       ('wind_direction_120m', 'hourly', '°', 'Wind direction at 120 meters'),
       ('wind_direction_180m', 'hourly', '°', 'Wind direction at 180 meters'),

       ('wind_gusts_10m', 'hourly', 'km/h', 'Wind gusts at 10 meters'),

       ('temperature_80m', 'hourly', '°C', 'Temperature at 80 meters'),
       ('temperature_120m', 'hourly', '°C', 'Temperature at 120 meters'),
       ('temperature_180m', 'hourly', '°C', 'Temperature at 180 meters'),

       ('soil_temperature_0cm', 'hourly', '°C', 'Soil temperature at 0 cm depth'),
       ('soil_temperature_6cm', 'hourly', '°C', 'Soil temperature at 6 cm depth'),
       ('soil_temperature_18cm', 'hourly', '°C', 'Soil temperature at 18 cm depth'),
       ('soil_temperature_54cm', 'hourly', '°C', 'Soil temperature at 54 cm depth'),

       ('soil_moisture_0_1cm', 'hourly', 'm³/m³', 'Soil moisture at 0–1 cm'),
       ('soil_moisture_1_3cm', 'hourly', 'm³/m³', 'Soil moisture at 1–3 cm'),
       ('soil_moisture_3_9cm', 'hourly', 'm³/m³', 'Soil moisture at 3–9 cm'),
       ('soil_moisture_9_27cm', 'hourly', 'm³/m³', 'Soil moisture at 9–27 cm'),
       ('soil_moisture_27_81cm', 'hourly', 'm³/m³', 'Soil moisture at 27–81 cm')
ON CONFLICT (name, resolution) DO NOTHING;

-- =========================
-- DAILY WEATHER PARAMETERS
-- =========================

INSERT INTO weather_parameters (name, resolution, unit, description)
VALUES ('weathercode', 'daily', NULL, 'Daily weather condition code'),
       ('temperature_2m_max', 'daily', '°C', 'Maximum daily temperature at 2 meters'),
       ('temperature_2m_min', 'daily', '°C', 'Minimum daily temperature at 2 meters'),
       ('apparent_temperature_max', 'daily', '°C', 'Maximum apparent temperature'),
       ('apparent_temperature_min', 'daily', '°C', 'Minimum apparent temperature'),
       ('sunrise', 'daily', 'ISO8601', 'Sunrise time'),
       ('sunset', 'daily', 'ISO8601', 'Sunset time'),
       ('daylight_duration', 'daily', 's', 'Total daylight duration'),
       ('sunshine_duration', 'daily', 's', 'Total sunshine duration'),
       ('uv_index_max', 'daily', NULL, 'Maximum UV index'),
       ('uv_index_clear_sky_max', 'daily', NULL, 'Maximum UV index under clear sky'),

       ('rain_sum', 'daily', 'mm', 'Total rain sum'),
       ('showers_sum', 'daily', 'mm', 'Total showers sum'),
       ('snowfall_sum', 'daily', 'cm', 'Total snowfall sum'),
       ('precipitation_sum', 'daily', 'mm', 'Total precipitation sum'),
       ('precipitation_hours', 'daily', 'h', 'Hours with precipitation'),
       ('precipitation_probability_max', 'daily', '%',
        'Maximum precipitation probability'),

       ('wind_speed_10m_max', 'daily', 'km/h', 'Maximum wind speed at 10 meters'),
       ('wind_gusts_10m_max', 'daily', 'km/h', 'Maximum wind gusts at 10 meters'),
       ('wind_direction_10m_dominant', 'daily', '°', 'Dominant wind direction'),

       ('shortwave_radiation_sum', 'daily', 'MJ/m²', 'Shortwave radiation sum'),
       ('et0_fao_evapotranspiration', 'daily', 'mm',
        'Reference evapotranspiration (ET₀)')
ON CONFLICT (name, resolution) DO NOTHING;

-- =========================
-- CURRENT WEATHER PARAMETERS
-- =========================

INSERT INTO weather_parameters (name, resolution, unit, description)
VALUES ('temperature_2m', 'current', '°C', 'Current air temperature'),
       ('relative_humidity_2m', 'current', '%', 'Current relative humidity'),
       ('apparent_temperature', 'current', '°C', 'Current apparent temperature'),
       ('is_day', 'current', NULL, 'Day or night indicator'),
       ('precipitation', 'current', 'mm', 'Current precipitation'),
       ('rain', 'current', 'mm', 'Current rain'),
       ('showers', 'current', 'mm', 'Current showers'),
       ('snowfall', 'current', 'cm', 'Current snowfall'),
       ('weathercode', 'current', NULL, 'Current weather condition code'),
       ('cloud_cover', 'current', '%', 'Current cloud cover'),
       ('pressure_msl', 'current', 'hPa', 'Current mean sea level pressure'),
       ('surface_pressure', 'current', 'hPa', 'Current surface pressure'),
       ('wind_speed_10m', 'current', 'km/h', 'Current wind speed'),
       ('wind_direction_10m', 'current', '°', 'Current wind direction'),
       ('wind_gusts_10m', 'current', 'km/h', 'Current wind gusts')
ON CONFLICT (name, resolution) DO NOTHING;
