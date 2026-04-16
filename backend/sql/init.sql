-- SandbeltOS 数据库初始化脚本
-- 需要先安装 TimescaleDB 和 PostGIS 扩展

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;

-- 区域信息表（矢量）
CREATE TABLE IF NOT EXISTS regions (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    level       VARCHAR(20),
    geom        GEOMETRY(MULTIPOLYGON, 4326),
    area_km2    FLOAT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_regions_geom ON regions USING GIST(geom);

-- 生态指标时序表（超表）
CREATE TABLE IF NOT EXISTS eco_indicators (
    time        TIMESTAMPTZ NOT NULL,
    region_id   INTEGER REFERENCES regions(id),
    indicator   VARCHAR(50) NOT NULL,
    value       FLOAT NOT NULL,
    source      VARCHAR(30),
    resolution  VARCHAR(20),
    quality     SMALLINT DEFAULT 1
);
SELECT create_hypertable('eco_indicators', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_eco_region_indicator ON eco_indicators(region_id, indicator, time DESC);

-- 气象数据时序表
CREATE TABLE IF NOT EXISTS weather_data (
    time            TIMESTAMPTZ NOT NULL,
    region_id       INTEGER REFERENCES regions(id),
    precipitation   FLOAT,
    wind_speed      FLOAT,
    wind_direction  FLOAT,
    temperature     FLOAT,
    evapotranspiration FLOAT,
    soil_moisture   FLOAT
);
SELECT create_hypertable('weather_data', 'time', if_not_exists => TRUE);

-- 沙化风险评估记录
CREATE TABLE IF NOT EXISTS desertification_risk (
    time        TIMESTAMPTZ NOT NULL,
    region_id   INTEGER REFERENCES regions(id),
    risk_level  SMALLINT,
    risk_score  FLOAT,
    wind_erosion_modulus FLOAT,
    sand_fixation_amount FLOAT,
    factors     JSONB
);
SELECT create_hypertable('desertification_risk', 'time', if_not_exists => TRUE);

-- 造林记录表
CREATE TABLE IF NOT EXISTS afforestation_records (
    id          SERIAL PRIMARY KEY,
    region_id   INTEGER REFERENCES regions(id),
    year        INTEGER,
    species     VARCHAR(100),
    area_ha     FLOAT,
    density     INTEGER,
    survival_rate FLOAT,
    source      VARCHAR(50)
);

-- 预警记录表
CREATE TABLE IF NOT EXISTS alerts (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    region_id   INTEGER REFERENCES regions(id),
    alert_type  VARCHAR(50),
    severity    VARCHAR(20),
    message     TEXT,
    is_read     BOOLEAN DEFAULT FALSE
);
