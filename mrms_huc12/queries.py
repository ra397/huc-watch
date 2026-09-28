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