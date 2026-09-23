import numpy as np
from db import insert_huc12

d = np.load('LUT/huc12_mrms_flat.npz')
ids, idx, frac, area, groups = d['ids'], d['idx'], d['frac'], d['area'], d['groups']
n = len(ids)

huc_area = np.bincount(groups, weights=frac * area, minlength=n)

rows = [
    {"huc12": code, "area_km2": round(float(area), 2)}
    for code, area in zip(ids, huc_area)
]

insert_huc12(rows)