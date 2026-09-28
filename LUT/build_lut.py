# Build a flat HUC12 -> MRMS lookup table for np.bincount aggregation
# Usage: python build_lut.py [config.ini]
import configparser
import sys
from pathlib import Path
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

config_path = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / 'config.ini').resolve()
config = configparser.ConfigParser()
if not config.read(config_path):
    sys.exit(f"Config file not found: {config_path}")
base_dir = config_path.parent

grid = config['grid']
nx, ny = grid.getint('nx'), grid.getint('ny')
dx, dy = grid.getfloat('dx'), grid.getfloat('dy')
x0, y0 = grid.getfloat('x0'), grid.getfloat('y0')

shapefile_path = base_dir / config['features']['shapefile']

huc12s, huc12_ids = shp_to_geoms(str(shapefile_path), config['features']['id_field'])

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