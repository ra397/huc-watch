# Cron entry point: python -m process_mrms.process
import logging
import sys
from datetime import datetime, timezone
from process_mrms.db import get_conn, get_latest_obs_time, insert_huc12_mrms_2min, delete_older_than_24h
from process_mrms.discovery import find_pending, key_url
from process_mrms.rainfall import load_lut, read_mean_rain, build_rows

log = logging.getLogger('process_mrms.process')


def process_pending(conn, ids, idx, frac, groups, n):
    latest = get_latest_obs_time(conn)
    if latest is not None:
        latest = latest.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    log.info("Latest processed obs_time: %s", latest.isoformat() if latest else "none (initial run)")

    try:
        pending = find_pending(latest, now)
    except Exception:
        log.exception("Failed to list released MRMS files from S3; nothing processed")
        return 1

    if not pending:
        log.info("No newly released MRMS files")
        return 0

    for obs_time, key in pending:
        if key is None:
            log.warning("obs_time=%s: not in S3 listing although later files are released; "
                        "recording as missing", obs_time.isoformat())
            mean_rain = None
        else:
            try:
                mean_rain = read_mean_rain(key_url(key), idx, frac, groups, n)
            except Exception as e:
                log.error("obs_time=%s key=%s: failed to read (%s: %s); recording as no data",
                          obs_time.isoformat(), key, type(e).__name__, e, exc_info=True)
                mean_rain = None

        # Database errors propagate: continuing past one would break chronological ordering
        insert_huc12_mrms_2min(conn, build_rows(ids, obs_time, mean_rain))
        log.info("obs_time=%s key=%s: stored (%s)", obs_time.isoformat(), key,
                 "rainfall" if mean_rain is not None else "NULL")

    return 0


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    ids, idx, frac, groups = load_lut()
    n = len(ids)

    with get_conn() as conn:
        status = process_pending(conn, ids, idx, frac, groups, n)
        # Runs after inserts so the 24h window is measured from the newest obs_time
        deleted = delete_older_than_24h(conn)
        log.info("Deleted %d rows older than 24h before the latest obs_time", deleted)

    return status


if __name__ == '__main__':
    sys.exit(main())