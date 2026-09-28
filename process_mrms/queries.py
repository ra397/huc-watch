INSERT_HUC12_REGION = """
    INSERT INTO huc12_regions (huc12, area_km2)
    VALUES (%(huc12)s, %(area_km2)s)
    ON CONFLICT (huc12) DO NOTHING
"""

INSERT_HUC12_MRMS_2MIN = """
    INSERT INTO huc12_mrms_2min (huc12_id, obs_time, mean_rain_mm)
    SELECT id, %(obs_time)s, %(mean_rain_mm)s
    FROM huc12_regions
    WHERE huc12 = %(huc12)s
    ON CONFLICT (huc12_id, obs_time) DO NOTHING
"""

SELECT_LATEST_OBS_TIME = """
    SELECT max(obs_time) FROM huc12_mrms_2min
"""

DELETE_OLDER_THAN_24H = """
    DELETE FROM huc12_mrms_2min
    WHERE obs_time < (SELECT max(obs_time) FROM huc12_mrms_2min) - INTERVAL '24 hours'
"""

GET_ACCUMULATION = """
    WITH latest_obs AS (
        SELECT max(obs_time) AS latest_time
        FROM huc12_mrms_2min
    ),
    accumulation_times AS (
        SELECT
            latest_time - (n * INTERVAL '1 hour') AS obs_time
        FROM latest_obs
        CROSS JOIN generate_series(
            0,
            %s - 1
        ) AS n
    ),
    accumulation AS (
        SELECT
            m.huc12_id,
            SUM(m.mean_rain_mm) AS accumulation_mm
        FROM huc12_mrms_2min m
        JOIN accumulation_times t
            ON m.obs_time = t.obs_time
        GROUP BY m.huc12_id
    )
    SELECT
        r.id AS huc12_id,
        r.huc12,
        COALESCE(a.accumulation_mm, 0) AS accumulation_mm
    FROM huc12_regions r
    LEFT JOIN accumulation a
        ON a.huc12_id = r.id
    ORDER BY r.id;
"""