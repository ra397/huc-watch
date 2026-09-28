import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

BUCKET_URL = 'https://noaa-mrms-pds.s3.amazonaws.com'
PRODUCT_PREFIX = 'CONUS/RadarOnly_QPE_01H_00.00'
KEY_RE = re.compile(
    rf'^{re.escape(PRODUCT_PREFIX)}/\d{{8}}/MRMS_RadarOnly_QPE_01H_00\.00_(\d{{8}}-\d{{6}})\.grib2\.gz$'
)
S3_NS = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
OBS_INTERVAL = timedelta(minutes=2)
LISTING_TIMEOUT_S = 30


def key_url(key):
    return f"{BUCKET_URL}/{key}"


def list_released(day):
    """Return {obs_time: key} for every MRMS object released under the given UTC day prefix."""
    prefix = f"{PRODUCT_PREFIX}/{day:%Y%m%d}/"
    released = {}
    token = None
    while True:
        params = {'list-type': '2', 'delimiter': '/', 'prefix': prefix}
        if token:
            params['continuation-token'] = token
        with urllib.request.urlopen(f"{BUCKET_URL}/?{urllib.parse.urlencode(params)}",
                                    timeout=LISTING_TIMEOUT_S) as resp:
            root = ET.fromstring(resp.read())

        for key_el in root.findall('s3:Contents/s3:Key', S3_NS):
            m = KEY_RE.match(key_el.text)
            if not m:
                log.warning("Skipping unrecognised S3 key %s", key_el.text)
                continue
            obs_time = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
            released[obs_time] = key_el.text

        if root.findtext('s3:IsTruncated', namespaces=S3_NS) != 'true':
            return released
        token = root.findtext('s3:NextContinuationToken', namespaces=S3_NS)


def find_pending(latest, now):
    """Return [(obs_time, key or None)] to process, in chronological order.

    key is None for a timestamp absent from S3 even though a later file has
    already been released; it is recorded as missing so it isn't retried forever.
    """
    if latest is None:
        released = list_released(now.date())
        if not released:
            return []
        newest = max(released)
        return [(newest, released[newest])]

    start = latest + OBS_INTERVAL
    released = {}
    day = start.date()
    while day <= now.date():
        released.update(list_released(day))
        day += timedelta(days=1)

    released = {t: k for t, k in released.items() if t > latest}
    if not released:
        return []

    pending = []
    t = start
    while t <= max(released):
        pending.append((t, released.get(t)))
        t += OBS_INTERVAL
    # Keep any released file that falls off the 2-minute grid rather than dropping it
    pending += [(t, k) for t, k in released.items() if (t - start) % OBS_INTERVAL]
    return sorted(pending)
