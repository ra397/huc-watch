# mrms-huc12

Aggregates NOAA MRMS 1-hour radar-only precipitation (`RadarOnly_QPE_01H_00.00`) onto HUC12
watersheds every 2 minutes and stores the area-weighted mean rainfall per HUC12 in PostgreSQL.

The job runs from cron every 2 minutes. On each run it:

1. Reads the latest `obs_time` already stored in `huc12_mrms_2min`.
2. Lists the NOAA S3 bucket (`noaa-mrms-pds`) for that UTC day and any later days, to see which files
   have actually been released. Files are released about 3 minutes after their observation time.
3. Processes every newly released file in chronological order. It writes one row per HUC12 per
   observation time.
4. Deletes rows more than 24 hours older than the newest observation.

Missing or unreadable files are still recorded, as rows with `mean_rain_mm = NULL`, so they are never
retried forever. A timestamp counts as missing only once a later file has been released. Timestamps
that haven't been released yet are left for the next run.

## Project layout

```
mrms-huc12/
├── environment.yml          # conda environment
├── .env.example             # template for database connection settings
├── postgres/schema.sql      # tables and indexes
├── LUT/                     # offline lookup-table build
│   ├── config.ini           # grid definition + shapefile to rasterise
│   ├── build_lut.py         # builds huc12_mrms_flat.npz
│   ├── coverage.py          # fractional cell coverage of a polygon
│   ├── HUC12/huc12.shp      # HUC12 polygons (WBD HU12, Iowa)
│   └── huc12_mrms_flat.npz  # build output, used by seed and the cron job
└── mrms_huc12/              # runtime package
    ├── db.py, queries.py    # database access
    ├── discovery.py         # S3 listing → files to process
    ├── rainfall.py          # GRIB2 read + per-HUC12 aggregation
    ├── process.py           # cron entry point
    └── seed.py              # populates huc12_regions
```

## Prerequisites

- Linux with cron. Tested on Ubuntu 24.04, including under WSL2 (see [WSL notes](#wsl-notes)).
- PostgreSQL 16 (`sudo apt install postgresql`)
- Miniconda or Miniforge
- Outbound HTTPS to `noaa-mrms-pds.s3.amazonaws.com` (public bucket, no AWS credentials needed)

## 1. Python environment

```bash
git clone <repo-url> mrms-huc12
cd mrms-huc12
conda env create -f environment.yml
conda activate mrms-huc12
```

GDAL's GRIB2 driver is a separate conda-forge package (`libgdal-grib`). It is included in
`environment.yml`; without it GDAL cannot open the MRMS files. To check it is installed:

```bash
python -c "from osgeo import gdal; print(gdal.GetDriverByName('GRIB'))"   # must not print None
```

All commands below are run from the project root with the environment active.

## 2. Build the lookup table (LUT)

The LUT maps each HUC12 to the MRMS grid cells it overlaps, with the fraction of each cell covered.
A pre-built `LUT/huc12_mrms_flat.npz` is committed to the repo, so **you only need to rebuild it if
you change the grid or the shapefile.**

Settings live in `LUT/config.ini`. Relative paths are resolved from the folder containing the config
file.

| Section      | Key          | Meaning                                                             |
|--------------|--------------|---------------------------------------------------------------------|
| `[grid]`     | `nx`, `ny`   | Grid width/height in cells (MRMS CONUS: 7000 × 3500)                |
|              | `dx`, `dy`   | Cell size in degrees, positive (MRMS: 0.01)                         |
|              | `x0`, `y0`   | Top-left corner of the grid in degrees (MRMS: -130.0, 55.0)         |
| `[features]` | `shapefile`  | Polygon shapefile in EPSG:4326 (WGS 84 longitude/latitude)          |
|              | `id_field`   | Attribute holding each polygon's 12-character ID (`HUC_12`)         |
| `[output]`   | `path`       | Where to write the `.npz`                                           |

The grid must match the MRMS product. To read it from any MRMS file:

```bash
gdalinfo /vsigzip//vsicurl/https://noaa-mrms-pds.s3.amazonaws.com/CONUS/RadarOnly_QPE_01H_00.00/<YYYYMMDD>/MRMS_RadarOnly_QPE_01H_00.00_<YYYYMMDD-HHMMSS>.grib2.gz | grep -E 'Size is|Origin|Pixel Size'
```

Build (about 25 s for the 1,712 Iowa HUC12s):

```bash
python LUT/build_lut.py                    # uses LUT/config.ini
python LUT/build_lut.py path/to/other.ini  # or an alternative config
```

The cron job always reads `LUT/huc12_mrms_flat.npz` (see `LUT_PATH` in `process_mrms/__init__.py`).
If you change `[output] path`, update `LUT_PATH` to match.

## 3. Create the database

This setup uses a dedicated PostgreSQL cluster on port 5433, separate from the default cluster on
5432. If you'd rather use an existing server, skip the cluster step and adjust the port.

```bash
# Dedicated cluster (Debian/Ubuntu postgresql-common tooling)
sudo pg_createcluster 16 process_mrms --port=5433 --start
pg_lsclusters    # should show 16 process_mrms 5433 online

# Application role and database
sudo -u postgres psql -p 5433 -c "CREATE ROLE hydrobot LOGIN PASSWORD 'choose-a-password';"
sudo -u postgres createdb -p 5433 -O hydrobot process_mrms
```

To start the cluster automatically on boot: `sudo systemctl enable postgresql@16-mrms_huc12`.

## 4. Configure `.env`

```bash
cp .env.example .env
chmod 600 .env
```

Fill in the values you used above:

```ini
PGHOST=localhost
PGPORT=5433
PGDATABASE=mrms_huc12
PGUSER=hydrobot
PGPASSWORD=choose-a-password
```

These are standard libpq variables. The code loads `.env` from the project root, whatever directory
you run it from. **Never commit `.env`**; it is listed in `.gitignore`.

## 5. Apply the schema

```bash
set -a; source .env; set +a          # export PG* so psql uses them
psql -f postgres/schema.sql
```

This creates:

- `huc12_regions`: one row per HUC12, with its area.
- `huc12_mrms_2min`: primary key `(huc12_id, obs_time)`, which prevents duplicate rows.
- An index on `obs_time`, used by the "latest processed" lookup and the 24-hour cleanup.

`schema.sql` is not idempotent; run it once, on an empty database.

## 6. Seed HUC12 regions

```bash
python -m process_mrms.seed
psql -c "SELECT count(*) FROM huc12_regions;"    # 1712 for the bundled Iowa shapefile
```

Seeding is safe to re-run: existing HUC12s are skipped. If you rebuild the LUT with a different
shapefile, re-run the seed. It **adds** new HUC12s but does not remove ones that are no longer in
the LUT.

## 7. Test a run manually

```bash
python -m process_mrms.process
```

The first run (empty table) processes only the most recent released file for the current UTC day.
Later runs pick up from where the previous one stopped. Expected output:

```
... INFO mrms_huc12.process Latest processed obs_time: none (initial run)
... INFO mrms_huc12.process obs_time=2026-09-28T16:44:00+00:00 key=CONUS/.../MRMS_RadarOnly_QPE_01H_00.00_20260928-164400.grib2.gz: stored (rainfall)
... INFO mrms_huc12.process Deleted 0 rows older than 24h before the latest obs_time
```

Exit code 0 means success, including when there are no new files. A non-zero exit means the S3
listing or the database failed.

## 8. Schedule with cron

Get the absolute path of the environment's Python. Cron should call it directly, with no
`conda activate`:

```bash
conda activate mrms-huc12 && which python     # e.g. /home/<you>/miniconda3/envs/mrms-huc12/bin/python
mkdir -p logs
crontab -e
```

Add (replace both paths):

```cron
*/2 * * * * cd /home/<you>/mrms-huc12 && /usr/bin/flock -n /tmp/mrms_huc12.lock /home/<you>/miniconda3/envs/mrms-huc12/bin/python -m mrms_huc12.process >> logs/process.log 2>&1
```

- `cd` is required: log paths are relative to the project.
- `flock -n` skips a run if the previous one is still going, e.g. while catching up after downtime.
  Overlapping runs wouldn't create duplicates anyway, but they would do the same work twice.
- To confirm cron is running: `systemctl is-active cron`. To follow the log:
  `tail -f logs/process.log`.

To test in a cron-like environment before relying on the schedule:

```bash
env -i HOME=$HOME sh -c 'cd /home/<you>/mrms-huc12 && /home/<you>/miniconda3/envs/mrms-huc12/bin/python -m process_mrms.process'
```

### Log rotation (recommended)

The log grows by a few lines every 2 minutes. `/etc/logrotate.d/mrms-huc12`:

```
/home/<you>/mrms-huc12/logs/process.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
```

### WSL notes

- Cron needs systemd: `/etc/wsl.conf` must contain `[boot]` / `systemd=true` (then run
  `wsl --shutdown` from Windows and reopen).
- Cron only runs while the WSL VM is running, and WSL shuts down when idle with no open terminals.
  After a gap, the next run catches up on everything still in the bucket, oldest first.

## Operations

**Checking progress.** `obs_time` is `timestamptz`. psql shows it in the session time zone, so
convert to UTC to compare with MRMS file names:

```sql
SELECT obs_time AT TIME ZONE 'UTC' AS obs_utc,
       count(*)            AS hucs,
       count(mean_rain_mm) AS hucs_with_data,
       max(mean_rain_mm)   AS max_mm
FROM huc12_mrms_2min
GROUP BY 1 ORDER BY 1 DESC LIMIT 10;
```

`hucs_with_data = 0` means the file was missing or unreadable. Individual NULLs within a timestamp
are HUC12s with no radar coverage (MRMS marks those cells `-3`).

**Log messages to watch for** (every file-level message includes the observation time and S3 key):

| Message                                                   | Meaning                                                                              |
|-----------------------------------------------------------|--------------------------------------------------------------------------------------|
| `not in S3 listing although later files are released`     | NOAA skipped that timestamp; stored as NULL. This happens occasionally.              |
| `failed to read (<ExceptionType>: ...)`                   | File was listed but couldn't be downloaded or parsed; stored as NULL, with traceback. |
| `Failed to list released MRMS files from S3`              | Network/S3 problem; nothing recorded, retried on the next run. Exit code 1.          |
| Python traceback from psycopg                             | Database error; the current file is rolled back and retried on the next run.         |

**Reprocessing a timestamp.** Delete its rows. Note the job only moves forward from the latest
stored `obs_time`, so this re-runs a timestamp only if it is the newest one:

```sql
DELETE FROM huc12_mrms_2min WHERE obs_time = '2026-09-28 16:44:00+00';
```

**Retention.** Each run keeps 24 hours of data, measured back from the newest observation, not
from the wall clock. That is about 720 timestamps × 1,712 HUC12s ≈ 1.2 M rows.
