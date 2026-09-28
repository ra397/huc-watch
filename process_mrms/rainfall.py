import numpy as np
from osgeo import gdal
from process_mrms import LUT_PATH

gdal.UseExceptions()
gdal.SetConfigOption('GDAL_HTTP_MAX_RETRY', '5')
gdal.SetConfigOption('GDAL_HTTP_RETRY_DELAY', '1')


def load_lut(path=LUT_PATH):
    d = np.load(path)
    return d['ids'], d['idx'], d['frac'], d['groups']


def read_mean_rain(url, idx, frac, groups, n):
    ds = gdal.Open(f"/vsigzip//vsicurl/{url}")
    try:
        rain = ds.ReadAsArray().astype(np.float32).ravel()
    finally:
        ds = None
        gdal.VSICurlClearCache()

    if rain.size <= idx.max():
        raise ValueError(f"grid has {rain.size} cells, LUT expects more than {idx.max()}")

    # Negative values (-3) mark cells without radar coverage; exclude them from the weighted mean.
    # A HUC12 with no covered cells gets 0/0 = NaN, which build_rows stores as NULL.
    cell_rain = rain[idx]
    weights = np.where(cell_rain >= 0, frac, 0)
    frac_sum = np.bincount(groups, weights=weights, minlength=n)
    with np.errstate(invalid='ignore', divide='ignore'):
        mean_rain = np.bincount(groups, weights=cell_rain * weights, minlength=n) / frac_sum
    if not np.isfinite(mean_rain).any():
        raise ValueError("no finite rainfall values")
    return mean_rain


def build_rows(ids, obs_time, mean_rain):
    if mean_rain is None:
        return [{"huc12": code, "obs_time": obs_time, "mean_rain_mm": None} for code in ids]
    return [
        {"huc12": code, "obs_time": obs_time,
         "mean_rain_mm": round(float(rain), 2) if np.isfinite(rain) else None}
        for code, rain in zip(ids, mean_rain)
    ]
