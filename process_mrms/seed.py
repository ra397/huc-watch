# Seeds huc12_regions from the LUT: python -m process_mrms.seed
import numpy as np
from process_mrms import LUT_PATH
from process_mrms.db import get_conn, insert_huc12

d = np.load(LUT_PATH)
ids, idx, frac, area, groups = d['ids'], d['idx'], d['frac'], d['area'], d['groups']
n = len(ids)

huc_area = np.bincount(groups, weights=frac * area, minlength=n)

rows = [
    {"huc12": code, "area_km2": round(float(area), 2)}
    for code, area in zip(ids, huc_area)
]

with get_conn() as conn:
    insert_huc12(conn, rows)