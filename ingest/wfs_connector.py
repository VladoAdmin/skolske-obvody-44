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
from typing import Optional

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
    PSK WFS returns 4326 by default; this is a safety check.
    If coords are clearly in S-JTSK (EPSG:5514, easting ~500000..800000),
    attempts reprojection via pyproj.
    """
    geom = feature.get("geometry")
    if geom is None:
        return feature

    def _check_coord(coords) -> str:
        """Detect CRS from first coordinate pair."""
        if not coords:
            return "4326"
        first = coords
        # Flatten nested lists to get first number pair
        while isinstance(first, list):
            first = first[0]
        if isinstance(first, (int, float)) and len(coords) >= 2:
            x, y = coords[0], coords[1]
        else:
            return "4326"
        # S-JTSK (EPSG:5514): x ~ -400000 to -900000, y ~ -900000 to -1300000
        if -900000 < x < -400000 or -1300000 < y < -800000:
            return "5514"
        return "4326"

    # Only check point/first coord
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])

    detected = "4326"
    if geom_type == "Point" and coords:
        detected = _check_coord(coords)
    elif geom_type in ("MultiPolygon", "Polygon", "MultiLineString", "LineString") and coords:
        detected = _check_coord(coords[0][0] if coords and coords[0] else [])

    if detected == "5514":
        try:
            from pyproj import Transformer
            transformer = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)

            def _reproject_coords(c):
                if isinstance(c[0], (int, float)):
                    x, y = transformer.transform(c[0], c[1])
                    return [x, y]
                return [_reproject_coords(sub) for sub in c]

            feature["geometry"]["coordinates"] = _reproject_coords(coords)
        except ImportError:
            raise CRSError(
                "pyproj is required for CRS reprojection but is not installed. "
                "Run: pip install pyproj"
            )

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
