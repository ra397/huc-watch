import numpy as np
from osgeo import gdal
import sys
from datetime import datetime, timezone
from db import insert_huc12_mrms_2min

gdal.UseExceptions()
gdal.SetConfigOption('GDAL_HTTP_MAX_RETRY', '5')
gdal.SetConfigOption('GDAL_HTTP_RETRY_DELAY', '1')

url = 'https://noaa-mrms-pds.s3.amazonaws.com/CONUS/MultiSensor_QPE_01H_Pass1_00.00/20260922/MRMS_MultiSensor_QPE_01H_Pass1_00.00_20260922-010000.grib2.gz'
ds = gdal.Open(f"/vsigzip//vsicurl/{url}")
rain = ds.ReadAsArray().astype(np.float32).ravel()

d = np.load('LUT/huc12_mrms_flat.npz')
ids, idx, frac, area, groups = d['ids'], d['idx'], d['frac'], d['area'], d['groups']
n = len(ids)

frac_sum = np.bincount(groups, weights=frac, minlength=n)
huc_area = np.bincount(groups, weights=frac * area, minlength=n)
mean_rain = np.bincount(groups, weights=rain[idx] * frac, minlength=n) / frac_sum
volume = mean_rain * huc_area * 1e3

obs_time = datetime.strptime("20260922-010000", "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
obs_times = [obs_time] * n

rows = [
    {"huc12": code, "obs_time":  time,"mean_rain_mm": round(float(rain), 2)}
    for code, time, rain in zip(ids, obs_times, mean_rain)
]

insert_huc12_mrms_2min(rows)

print("Done")
ds = None
gdal.VSICurlClearCache()

sys.exit(0)