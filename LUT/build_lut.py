# Build a flat HUC12 -> MRMS lookup table for np.bincount aggregation
from shapely.geometry import shape
import shapefile
from coverage import coverage
import numpy as np

def shp_to_geoms(path, id_field="HUC_12"):
    """One (Multi)Polygon per shapefile record, in record order (index == FID)."""
    sf = shapefile.Reader(path)
    geoms = [shape(s.__geo_interface__) for s in sf.shapes()]
    ids = [rec[id_field] for rec in sf.records()]
    return geoms, ids

# MRMS GRID
nx, ny = 7000, 3500
dx, dy = 0.01, 0.01
x0, y0 = -130.0, 55.0

huc12s, huc12_ids = shp_to_geoms('HUC12/huc12.shp', 'HUC_12')

all_idx, all_frac, all_area, all_groups = [], [], [], []

for i, poly in enumerate(huc12s):
    idx, frac, area = coverage(poly, x0=x0, y0=y0, dx=dx, dy=dy, nx=nx, ny=ny)
    idx, frac, area = np.asarray(idx), np.asarray(frac), np.asarray(area)

    keep = frac > 0  # drop bounding-box cells that don't touch the polygon
    all_idx.append(idx[keep])
    all_frac.append(frac[keep])
    all_area.append(area[keep])
    all_groups.append(np.full(keep.sum(), i))

np.savez('huc12_mrms_flat.npz',
         ids=np.asarray(huc12_ids),
         idx=np.concatenate(all_idx).astype(np.int32),
         frac=np.concatenate(all_frac).astype(np.float16),
         area=np.concatenate(all_area).astype(np.float16),
         groups=np.concatenate(all_groups).astype(np.int32))