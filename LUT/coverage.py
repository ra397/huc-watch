import numpy as np
import shapely
from pyproj import Geod

geod = Geod(ellps="WGS84")

def coverage(poly, x0, y0, dx, dy, nx, ny):
    """North-up grid; (x0, y0) is the top-left corner, dx/dy are positive cell sizes."""
    minx, miny, maxx, maxy = poly.bounds
    c0, c1 = max(int((minx - x0) // dx), 0), min(int((maxx - x0) // dx) + 1, nx)
    r0, r1 = max(int((y0 - maxy) // dy), 0), min(int((y0 - miny) // dy) + 1, ny)
    cols, rows = np.meshgrid(np.arange(c0, c1), np.arange(r0, r1))
    L, T = x0 + cols * dx, y0 - rows * dy
    cells = shapely.box(L, T - dy, L + dx, T)
    frac = shapely.area(shapely.intersection(cells, poly)) / (dx * dy)
    area = []
    for cell in cells.ravel():
        area_m2 = geod.geometry_area_perimeter(cell)[0]
        area_km2 = area_m2 / 1e6
        area.append(area_km2)
    idx_1d = (rows.ravel() * nx + cols.ravel()).tolist()
    return idx_1d, frac.ravel(), area