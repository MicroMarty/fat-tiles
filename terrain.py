"""Terrain analysis in spherical Web Mercator; no network or UI dependencies."""
import io
import math
import re
from dataclasses import dataclass

import numpy as np
from PIL import Image

SIZE = 256
RADIUS = 6378137.0
MAX_LAT = 85.0511287798066
MAX_ZOOM = 14
MAX_TILES = 2000
EVEREST_METRES = 8848.86
DEFAULT_COLOR = "#2684ff"
FLAT_EPS = 1e-7  # dimensionless gradient, numerical flatness only


def decode_terrarium(data):
    with Image.open(io.BytesIO(data)) as image:
        if image.size != (SIZE, SIZE):
            raise ValueError("La tuile DEM doit mesurer 256 × 256 pixels.")
        rgba = np.array(image.convert("RGBA"), dtype=np.float64)
    h = rgba[:, :, 0] * 256 + rgba[:, :, 1] + rgba[:, :, 2] / 256 - 32768
    # Black is outside the physical DEM range; zero metres is valid (128,0,0).
    h[(rgba[:, :, 3] == 0) | (h < -12000) | (h > 10000)] = np.nan
    return h


def tile_position(lon, lat, z):
    n = 2**z
    lat = max(-MAX_LAT, min(MAX_LAT, lat))
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, max(0.0, min(float(n), y))


def row_latitudes(z, y):
    world_y = (y * SIZE + np.arange(SIZE) + 0.5) / (SIZE * 2**z)
    return np.arctan(np.sinh(math.pi * (1 - 2 * world_y)))


def ground_resolution(z, y):
    return (2 * math.pi * RADIUS / (SIZE * 2**z)) * np.cos(row_latitudes(z, y))


def horn(padded, spacing):
    """3x3 Horn; x increases east, raster y south; downhill azimuth clockwise N."""
    a, b, c = padded[:-2, :-2], padded[:-2, 1:-1], padded[:-2, 2:]
    d, e, f = padded[1:-1, :-2], padded[1:-1, 1:-1], padded[1:-1, 2:]
    g, h, i = padded[2:, :-2], padded[2:, 1:-1], padded[2:, 2:]
    spacing = np.asarray(spacing)
    if spacing.ndim == 1:
        spacing = spacing[:, None]
    dx = ((c + 2*f + i) - (a + 2*d + g)) / (8 * spacing)
    dy = ((g + 2*h + i) - (a + 2*b + c)) / (8 * spacing)
    magnitude = np.hypot(dx, dy)
    slope = np.degrees(np.arctan(magnitude))
    aspect = np.degrees(np.arctan2(-dx, dy)) % 360
    valid = np.logical_and.reduce([np.isfinite(v) for v in (a,b,c,d,e,f,g,h,i)])
    elevation = np.where(valid, e, np.nan)
    slope = np.where(valid, slope, np.nan)
    aspect = np.where(valid & (magnitude > FLAT_EPS), aspect, np.nan)
    result = np.stack((elevation, slope, aspect)).astype("<f4")
    # Rounding to float32 can turn 359.999999 into 360.
    result[2] %= 360
    return result


def padded_tile(z, x, y, load):
    """Only a one-pixel halo, with true neighbours; no synthetic edge gradients."""
    out = np.full((258, 258), np.nan, dtype=np.float64)
    n = 2**z
    for oy in (-1, 0, 1):
        yy = y + oy
        if not 0 <= yy < n:
            continue  # Mercator north/south limits have no neighbours.
        dest_y = slice(0, 1) if oy == -1 else slice(257,258) if oy == 1 else slice(1,257)
        src_y = slice(255,256) if oy == -1 else slice(0,1) if oy == 1 else slice(None)
        for ox in (-1, 0, 1):
            dest_x = slice(0,1) if ox == -1 else slice(257,258) if ox == 1 else slice(1,257)
            src_x = slice(255,256) if ox == -1 else slice(0,1) if ox == 1 else slice(None)
            out[dest_y, dest_x] = load(z, (x + ox) % n, yy)[src_y, src_x]
    return out


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} : nombre fini attendu.")
    return float(value)


@dataclass(frozen=True)
class Filters:
    altitude: tuple
    slope: tuple
    aspects: tuple
    flats: bool = True
    opacity: int = 175
    color: str = DEFAULT_COLOR

    @classmethod
    def parse(cls, obj):
        if not isinstance(obj, dict):
            raise ValueError("Filtres manquants.")
        ranges = []
        for key, lo, hi in (("altitude", 0, EVEREST_METRES), ("slope", 0, 90)):
            values = obj.get(key)
            if not isinstance(values, list) or len(values) != 2:
                raise ValueError(f"Intervalle {key} invalide.")
            a, b = [finite_number(v, key) for v in values]
            if not lo <= a <= b <= hi:
                raise ValueError(f"Intervalle {key} hors limites ou inversé.")
            ranges.append((a, b))
        aspects = obj.get("aspects")
        if not isinstance(aspects, list) or any(type(a) is not int or not 0 <= a <= 7 for a in aspects):
            raise ValueError("Orientations invalides.")
        flats = obj.get("flats", True)
        if type(flats) is not bool:
            raise ValueError("Le choix des terrains plats doit être booléen.")
        opacity = obj.get("opacity", 175)
        if type(opacity) is not int or not 0 <= opacity <= 255:
            raise ValueError("Opacité invalide.")
        color = obj.get("color", DEFAULT_COLOR)
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Couleur invalide : utilisez un code comme #2684ff.")
        return cls(*ranges, tuple(sorted(set(aspects))), flats, opacity, color.lower())


def selection(metrics, filters):
    h, s, a = metrics
    valid = np.isfinite(h) & np.isfinite(s)
    sector = np.floor((np.nan_to_num(a) + 22.5) % 360 / 45).astype(np.int8)
    direction = np.isfinite(a) & np.isin(sector, filters.aspects)
    if filters.flats:
        direction |= ~np.isfinite(a) & np.isfinite(s) & (s <= math.degrees(math.atan(FLAT_EPS)) * 1.001)
    return valid & (h >= filters.altitude[0]) & (h <= filters.altitude[1]) & (s >= filters.slope[0]) & (s <= filters.slope[1]) & direction


def relief_rgba(metrics):
    h, s, a = metrics
    shade = np.sin(np.radians(45)) * np.cos(np.radians(s)) + np.cos(np.radians(45)) * np.sin(np.radians(s)) * np.cos(np.radians(np.nan_to_num(a) - 315))
    shade = 0.43 + 0.57 * np.clip(shade, 0, 1)
    stops = [-12000, -1, 0, 700, 1700, 2800, 4200, 10000]
    colors = np.array([[32,73,88],[76,116,130],[103,132,115],[138,151,124],[180,181,157],[204,201,181],[237,235,222],[250,249,244]])
    rgba = np.zeros((256,256,4), dtype=np.uint8)
    for channel in range(3):
        rgba[:,:,channel] = np.nan_to_num(np.interp(h, stops, colors[:,channel]) * shade).astype(np.uint8)
    rgba[:,:,3] = np.where(np.isfinite(h), 255, 0)
    return rgba


def clip_mask(z, x, y, bounds):
    w, s, e, n = bounds
    x0, y0 = tile_position(w, n, z)
    x1, y1 = tile_position(e, s, z)
    px = x + (np.arange(256) + .5) / 256
    py = y + (np.arange(256) + .5) / 256
    return ((px >= x0) & (px < x1))[None,:] & ((py >= y0) & (py < y1))[:,None]


def png_tile(metrics, filters=None, bounds=None, coords=None, composite=False):
    rgba = relief_rgba(metrics) if composite or filters is None else np.zeros((256,256,4), dtype=np.uint8)
    if filters is not None:
        mask = selection(metrics, filters)
        color = np.array([int(filters.color[i:i+2],16) for i in (1,3,5)])
        if composite:
            alpha = filters.opacity / 255
            rgba[mask,:3] = np.rint(rgba[mask,:3] * (1-alpha) + color * alpha).astype(np.uint8)
        else:
            rgba[mask,:3] = color
            rgba[mask,3] = filters.opacity
    if bounds is not None:
        rgba[~clip_mask(*coords, bounds), 3] = 0
    out = io.BytesIO()
    Image.fromarray(rgba).save(out, format="PNG")
    return out.getvalue()


def plan_region(obj):
    bounds = obj.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != 4:
        raise ValueError("Dessinez une zone à exporter.")
    w,s,e,n = [finite_number(v, "Coordonnée") for v in bounds]
    if not (-180 <= w < e <= 180 and -MAX_LAT <= s < n <= MAX_LAT):
        raise ValueError("Zone invalide. Pour traverser l’antiméridien, exportez deux rectangles séparés.")
    zmin, zmax = obj.get("minzoom"), obj.get("maxzoom")
    if type(zmin) is not int or type(zmax) is not int or not 0 <= zmin <= zmax <= MAX_ZOOM:
        raise ValueError(f"Choisissez des zooms ordonnés entre 0 et {MAX_ZOOM}.")
    ranges, count = [], 0
    for z in range(zmin, zmax+1):
        x0,y0 = tile_position(w,n,z)
        x1,y1 = tile_position(e,s,z)
        # Half-open bounds; tolerance prevents floating roundoff adding a tile.
        xa,ya = math.floor(x0+1e-10), math.floor(y0+1e-10)
        xb,yb = math.ceil(x1-1e-10)-1, math.ceil(y1-1e-10)-1
        xa, ya = min(2**z-1, xa), min(2**z-1, ya)
        xb, yb = max(xa, xb), max(ya, yb)
        c = (xb-xa+1)*(yb-ya+1)
        count += c
        ranges.append((z,xa,ya,xb,yb,c))
    if count > MAX_TILES:
        raise ValueError(f"{count:,} tuiles : limite de {MAX_TILES:,}. Réduisez la zone ou le zoom maximal.")
    tiles = [(z,x,y) for z,xa,ya,xb,yb,c in ranges for x in range(xa,xb+1) for y in range(ya,yb+1)]
    sources = set()
    for z,x,y in tiles:
        sources.update((z,(x+ox) % 2**z,y+oy) for ox in (-1,0,1) for oy in (-1,0,1) if 0 <= y+oy < 2**z)
    area = RADIUS**2 * math.radians(e-w) * (math.sin(math.radians(n))-math.sin(math.radians(s))) / 1e6
    return {"bounds":[w,s,e,n], "minzoom":zmin, "maxzoom":zmax, "count":count, "sources":sorted(sources), "tiles":tiles, "area_km2":area, "levels":[{"zoom":r[0],"count":r[5]} for r in ranges]}
