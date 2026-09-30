GRANT ALL ON SCHEMA public TO hydrobot;

SET ROLE hydrobot;

CREATE TABLE IF NOT EXISTS huc12_regions (
    id smallserial PRIMARY KEY,
    huc12 char(12) NOT NULL UNIQUE,
    area_km2 double precision NOT NULL
);

CREATE TABLE IF NOT EXISTS huc12_mrms_2min (
    huc12_id smallint NOT NULL REFERENCES huc12_regions(id),
    obs_time timestamptz NOT NULL,
    mean_rain_mm real,
    PRIMARY KEY (huc12_id, obs_time)
);

CREATE INDEX ON huc12_mrms_2min (obs_time);

CREATE TABLE IF NOT EXISTS users (
    id    serial PRIMARY KEY,
    email text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS verifications (
    id         bigserial PRIMARY KEY,
    user_id    integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code       char(6) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '5 minutes',
    consumed   boolean NOT NULL DEFAULT false
);

CREATE INDEX ON verifications (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS sessions (
    id         serial PRIMARY KEY,
    user_id    integer NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,  -- one session per user
    token      text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL
);

CREATE TABLE notifications (
    id                  serial PRIMARY KEY,
    user_id             integer  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    huc_id              smallint NOT NULL REFERENCES huc12_regions(id),
    threshold           numeric(6,2) NOT NULL CHECK (threshold > 0),
    accumulation_period integer      NOT NULL CHECK (accumulation_period > 0),
    UNIQUE (user_id, huc_id, threshold, accumulation_period)
);