GRANT ALL ON SCHEMA public TO hydrobot;

SET ROLE hydrobot;

CREATE TABLE huc12_regions (
    id smallserial PRIMARY KEY,
    huc12 char(12) NOT NULL UNIQUE,
    area_km2 double precision NOT NULL
);

CREATE TABLE huc12_mrms_2min (
    huc12_id smallint NOT NULL REFERENCES huc12_regions(id),
    obs_time timestamptz NOT NULL,
    mean_rain_mm real,
    PRIMARY KEY (huc12_id, obs_time)
);

CREATE INDEX ON huc12_mrms_2min (obs_time);