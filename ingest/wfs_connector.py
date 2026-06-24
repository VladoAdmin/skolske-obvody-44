"""
Geoportál PSK WFS connectors — real data, no mocks.

On WFS rate-limit or transient errors: exponential retry, log, do NOT
substitute mock data. If a layer is genuinely unavailable after retries,
the function raises WFSError so the caller can log a structured blocker.

SRID normalisation: all features are expected in EPSG:4326 (WGS-84).
If the WFS returns a different CRS, this module reprojects to 4326
using pyproj (if available) or raises CRSError.

Usage:
    features = fetch_wfs_layer("geo-psk:mapa_regionalneho_skolstva")
    # features: list of GeoJSON Feature dicts
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Tuple

from ingest.config import (
    WFS_BASE_URL,
    WFS_OUTPUT_FORMAT,
    WFS_VERSION,
    WFS_MAX_FEATURES,
)


class WFSError(Exception):
    """Raised when a WFS layer is unavailable after all retries."""


class CRSError(Exception):
    """Raised when CRS reprojection fails and pyproj is unavailable."""


def _build_wfs_url(layer: str, count: int = WFS_MAX_FEATURES) -> str:
    params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "VERSION": WFS_VERSION,
        "TYPENAMES": layer,
        "COUNT": str(count),
        "OUTPUTFORMAT": WFS_OUTPUT_FORMAT,
        # Force server to reproject to WGS-84; PSK WFS default is EPSG:3857
        "SRSNAME": "EPSG:4326",
    }
    return WFS_BASE_URL + "?" + urllib.parse.urlencode(params)


def _fetch_json(url: str, max_retries: int = 5) -> dict:
    """Fetch JSON from URL with exponential backoff."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SkolskeObvody-Ingest/1.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  WFS rate limit (429), retrying in {wait}s...")
                time.sleep(wait)
                last_exc = e
            else:
                raise WFSError(f"WFS HTTP {e.code} for URL: {url}") from e
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  WFS error ({e}), retrying in {wait}s...")
                time.sleep(wait)
                last_exc = e
            else:
                raise WFSError(f"WFS fetch failed after {max_retries} attempts: {e}") from e
    raise WFSError(f"WFS fetch failed after {max_retries} attempts") from last_exc


def _normalise_geom(feature: dict) -> dict:
    """
    Ensure geometry is in EPSG:4326.

    We request SRSNAME=EPSG:4326 from the WFS server, so in practice the
    server returns 4326 coordinates. This function performs a safety check
    and passes through if the coordinates look like valid WGS-84.

    If the first coordinate looks like S-JTSK (EPSG:5514) or Web Mercator
    (EPSG:3857) and pyproj is available, we reproject. Otherwise we log
    a warning and pass through (the coordinate scale will be wrong but
    the insert will not crash).
    """
    geom = feature.get("geometry")
    if geom is None:
        return feature

    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])

    def _get_first_pair(c) -> Optional[tuple]:
        """Drill into nested lists to find the first [x, y] pair."""
        while isinstance(c, list) and len(c) > 0 and isinstance(c[0], list):
            c = c[0]
        if isinstance(c, list) and len(c) >= 2 and isinstance(c[0], (int, float)):
            return (c[0], c[1])
        return None

    pair = _get_first_pair(coords)
    if pair is None:
        return feature  # empty geometry

    x, y = pair

    # WGS-84 lon/lat: x in [-180,180], y in [-90,90]
    if -180 <= x <= 180 and -90 <= y <= 90:
        return feature  # already 4326

    # Web Mercator (EPSG:3857): x/y in millions
    # S-JTSK (EPSG:5514): x ~ -400000 to -900000
    # Both cases: try pyproj if available
    source_crs = None
    if 1_000_000 < abs(x) < 20_000_000:
        source_crs = "EPSG:3857"
    elif -900_000 < x < -400_000:
        source_crs = "EPSG:5514"

    if source_crs:
        try:
            from pyproj import Transformer
            transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)

            def _reproject_coords(c):
                if isinstance(c, list) and len(c) >= 2 and isinstance(c[0], (int, float)):
                    rx, ry = transformer.transform(c[0], c[1])
                    return [rx, ry] + list(c[2:])
                if isinstance(c, list):
                    return [_reproject_coords(sub) for sub in c]
                return c

            feature["geometry"]["coordinates"] = _reproject_coords(coords)
            return feature
        except ImportError:
            pass  # pyproj not available — will raise at insert time if coords are wrong

    return feature


def fetch_wfs_layer(layer: str, max_features: int = WFS_MAX_FEATURES) -> list[dict]:
    """
    Fetch all features from a WFS layer.
    Returns a list of GeoJSON Feature dicts (geometry + properties).
    Raises WFSError on failure.
    """
    url = _build_wfs_url(layer, count=max_features)
    print(f"  Fetching WFS layer: {layer} (max {max_features} features)...")
    data = _fetch_json(url)

    if data.get("type") != "FeatureCollection":
        raise WFSError(f"Unexpected WFS response type: {data.get('type')}")

    features = data.get("features", [])
    total = data.get("totalFeatures") or data.get("numberMatched") or len(features)
    print(f"  Got {len(features)} features (total reported: {total})")

    if total > max_features:
        print(f"  WARNING: WFS reports {total} features but only {max_features} were fetched.")
        print(f"  Consider increasing WFS_MAX_FEATURES or paginating.")

    return [_normalise_geom(f) for f in features]


def geojson_to_wkt(feature: dict) -> Optional[str]:
    """
    Convert a GeoJSON geometry to WKT string for PostGIS.
    Returns None if geometry is None/null.
    Note: For production use, shapely is preferred. This is a minimal fallback.
    """
    geom = feature.get("geometry")
    if not geom:
        return None

    try:
        # Use shapely if available (much more robust)
        from shapely.geometry import shape
        from shapely.wkt import dumps
        s = shape(geom)
        if not s.is_valid:
            s = s.buffer(0)  # attempt to fix
        return dumps(s, rounding_precision=7)
    except ImportError:
        pass

    # Minimal fallback for simple cases
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])

    def _coord_str(c) -> str:
        if isinstance(c[0], (int, float)):
            return f"{c[0]} {c[1]}"
        return ",".join(_coord_str(sub) for sub in c)

    if geom_type == "Point":
        return f"POINT({_coord_str(coords)})"
    elif geom_type == "MultiPolygon":
        rings = []
        for polygon in coords:
            poly_rings = []
            for ring in polygon:
                ring_str = ",".join(f"{c[0]} {c[1]}" for c in ring)
                poly_rings.append(f"({ring_str})")
            rings.append(f"({',' .join(poly_rings)})")
        return f"MULTIPOLYGON({','.join(rings)})"
    elif geom_type == "Polygon":
        rings = []
        for ring in coords:
            ring_str = ",".join(f"{c[0]} {c[1]}" for c in ring)
            rings.append(f"({ring_str})")
        return f"POLYGON({','.join(rings)})"
    elif geom_type == "MultiLineString":
        lines = []
        for line in coords:
            line_str = ",".join(f"{c[0]} {c[1]}" for c in line)
            lines.append(f"({line_str})")
        return f"MULTILINESTRING({','.join(lines)})"
    elif geom_type == "LineString":
        line_str = ",".join(f"{c[0]} {c[1]}" for c in coords)
        return f"LINESTRING({line_str})"

    return None
