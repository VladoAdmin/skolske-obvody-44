"""
MV SR Register adries — address point ingestion for PSK municipalities.

The Register adries is published as open data by MV SR.
Official download: https://www.minv.sk/?register-adries

Download approach:
  1. Check if a local cache file exists in ingest/sources/register_adries_psk.csv
  2. Attempt to download from known data.gov.sk resource
  3. Attempt INSPIRE Atom feed
  4. If all fail: log structured BLOCKER and return empty list.

This is a HARD DEPENDENCY for Š1 and P-b. If unavailable:
  - Š1 (coverage check) = INCOMPLETE for affected municipalities
  - P-b (distance check) = INCOMPLETE for affected municipalities

Sprint 1 target: load address points for Prešov + 3 sample municipalities.
If full PSK is too heavy, curated sample of 4 obce (PRD §8).

NOTE: The Register adries bulk download (full SR) is ~300MB as SHP ZIP.
This module fetches only PSK-relevant subset when possible.

Data format: CSV or SHP with at minimum:
  - súpisné číslo (house number)
  - ulica (street name)
  - obec (municipality)
  - GPS WGS-84 coordinates (lat, lon)
"""

import csv
import json
import os
import sys
import io
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from ingest.config import (
    validate_config,
    QUALITY_ADDRESS_POINTS,
)
from ingest.supabase_client import upsert

CACHE_DIR = Path(__file__).parent / "sources"
CACHE_FILE_CSV = CACHE_DIR / "register_adries_psk.csv"
CACHE_FILE_GEOJSON = CACHE_DIR / "register_adries_psk.geojson"

# PSK municipality codes to filter (target Prešov + 3 sample municipalities)
# Prešov: IDN4=519212, Varhaňovce: 518344, Kokošovce: 519031, Haniska: 518522
PSK_TARGET_MUNICIPALITIES = {
    "519212": "Prešov",
    "518344": "Varhaňovce",
    "519031": "Kokošovce",
    "518522": "Haniska",
}

# Known data.gov.sk resource URLs (may change over time)
# These are the last known working download URLs for Register adries.
REGISTER_ADRIES_DOWNLOAD_URLS = [
    # Full Slovakia SHP ZIP - large
    "https://data.gov.sk/dataset/cd0b40e3-b3dc-4e55-b28c-8fa9bc0bc3f7/resource/69d29df1-9b8e-4e06-a6f6-7ffeaafee9ef/download/aa_sr_shp.zip",
    # Alternative CSV format
    "https://data.gov.sk/dataset/register-adries/resource/addresses-psk.csv",
    # INSPIRE endpoint
    "https://inspire.gov.sk/atom/ds/ad/PSK/addresses.zip",
]


class AddressPointsUnavailable(Exception):
    """Register adries is not accessible from this environment."""


def load_address_points_from_cache() -> list[dict]:
    """Load from local cache if available."""
    if CACHE_FILE_CSV.exists():
        print(f"  Loading address points from cache: {CACHE_FILE_CSV}")
        points = []
        with open(CACHE_FILE_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lat = float(row.get("lat") or row.get("latitude") or row.get("gps_lat") or 0)
                    lon = float(row.get("lon") or row.get("longitude") or row.get("gps_lon") or 0)
                    if lat == 0 or lon == 0:
                        continue
                    points.append({
                        "municipality_code": row.get("municipality_code", ""),
                        "municipality_name": row.get("municipality_name", ""),
                        "street": row.get("street") or row.get("ulica") or "",
                        "house_number": row.get("house_number") or row.get("supisne_cislo") or "",
                        "postal_code": row.get("postal_code") or row.get("psc") or "",
                        "lat": lat,
                        "lon": lon,
                    })
                except (ValueError, TypeError):
                    continue
        print(f"  Loaded {len(points)} address points from cache")
        return points

    if CACHE_FILE_GEOJSON.exists():
        print(f"  Loading address points from GeoJSON cache: {CACHE_FILE_GEOJSON}")
        with open(CACHE_FILE_GEOJSON, encoding="utf-8") as f:
            data = json.load(f)
        points = []
        for feat in data.get("features", []):
            props = feat["properties"]
            geom = feat.get("geometry", {})
            if geom and geom.get("type") == "Point":
                coords = geom["coordinates"]
                points.append({
                    "municipality_code": str(props.get("municipality_code", "")),
                    "municipality_name": props.get("municipality_name", ""),
                    "street": props.get("street") or props.get("ulica") or "",
                    "house_number": props.get("house_number") or "",
                    "postal_code": props.get("postal_code") or "",
                    "lat": coords[1],
                    "lon": coords[0],
                })
        print(f"  Loaded {len(points)} address points from GeoJSON cache")
        return points

    return []


def try_download_register_adries() -> Optional[list[dict]]:
    """
    Attempt to download Register adries from known URLs.
    Returns list of address point dicts, or None if all sources fail.
    """
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for url in REGISTER_ADRIES_DOWNLOAD_URLS:
        try:
            print(f"  Attempting download from: {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "SkolskeObvody-Ingest/1.0"})
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                ct = resp.headers.get("Content-Type", "")
                data = resp.read()

                if not data or len(data) < 1000:
                    print(f"  Too small response ({len(data)} bytes), skipping")
                    continue

                print(f"  Downloaded {len(data)} bytes, CT: {ct}")

                # Parse based on content type
                if "zip" in ct.lower() or url.endswith(".zip"):
                    return _parse_zip_archive(data)
                elif "csv" in ct.lower() or url.endswith(".csv"):
                    return _parse_csv_data(data.decode("utf-8", errors="replace"))
                elif "json" in ct.lower():
                    geo = json.loads(data)
                    return _parse_geojson(geo)

        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} for {url}")
        except Exception as e:
            print(f"  Error for {url}: {e}")

    return None


def _parse_zip_archive(data: bytes) -> Optional[list[dict]]:
    """Extract and parse SHP/CSV from ZIP archive."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            print(f"  ZIP contents: {names[:10]}")

            # Try CSV first
            csv_files = [n for n in names if n.lower().endswith(".csv")]
            for csv_name in csv_files:
                with zf.open(csv_name) as f:
                    content = f.read().decode("utf-8", errors="replace")
                    return _parse_csv_data(content)

            # Try GeoJSON
            json_files = [n for n in names if n.lower().endswith(".geojson") or n.lower().endswith(".json")]
            for json_name in json_files:
                with zf.open(json_name) as f:
                    content = json.loads(f.read())
                    return _parse_geojson(content)

    except Exception as e:
        print(f"  ZIP parse error: {e}")
    return None


def _parse_csv_data(content: str) -> list[dict]:
    """Parse CSV data into address point dicts."""
    points = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        try:
            # Try common column name patterns
            lat = _get_coord(row, ["lat", "latitude", "gps_lat", "y", "SUP_SURAD_Y"])
            lon = _get_coord(row, ["lon", "longitude", "gps_lon", "x", "SUP_SURAD_X"])
            if lat is None or lon is None:
                continue
            points.append({
                "municipality_code": str(row.get("municipality_code") or row.get("KOD_OBCE") or ""),
                "municipality_name": row.get("municipality_name") or row.get("OBEC") or "",
                "street": row.get("street") or row.get("ULICA") or row.get("ULICA_NAZOV") or "",
                "house_number": row.get("house_number") or row.get("SUP_CISLO") or "",
                "postal_code": row.get("postal_code") or row.get("PSC") or "",
                "lat": lat,
                "lon": lon,
            })
        except (ValueError, TypeError):
            continue
    return points


def _get_coord(row: dict, keys: list[str]) -> Optional[float]:
    for k in keys:
        v = row.get(k)
        if v is not None and v != "":
            try:
                f = float(v.replace(",", ".") if isinstance(v, str) else v)
                if f != 0:
                    return f
            except (ValueError, AttributeError):
                pass
    return None


def _parse_geojson(data: dict) -> list[dict]:
    """Parse GeoJSON FeatureCollection into address point dicts."""
    points = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if geom and geom.get("type") == "Point":
            coords = geom["coordinates"]
            points.append({
                "municipality_code": str(props.get("KOD_OBCE") or props.get("municipality_code") or ""),
                "municipality_name": props.get("OBEC") or props.get("municipality_name") or "",
                "street": props.get("ULICA") or props.get("street") or "",
                "house_number": props.get("SUP_CISLO") or props.get("house_number") or "",
                "postal_code": props.get("PSC") or props.get("postal_code") or "",
                "lat": coords[1],
                "lon": coords[0],
            })
    return points


def load_address_points(target_municipalities: dict = PSK_TARGET_MUNICIPALITIES) -> list[dict]:
    """
    Load address points for target municipalities.
    Returns list of dicts suitable for so_address_points upsert.

    Priority order:
    1. Local cache
    2. Download from known URLs
    3. Raise AddressPointsUnavailable (caller logs as BLOCKER)
    """
    # 1. Try cache
    points = load_address_points_from_cache()
    if points:
        return _filter_and_format(points, target_municipalities)

    # 2. Try download
    downloaded = try_download_register_adries()
    if downloaded:
        # Cache locally
        print(f"  Caching {len(downloaded)} address points to {CACHE_FILE_CSV}")
        _save_to_csv(downloaded)
        return _filter_and_format(downloaded, target_municipalities)

    # 3. Fail with structured error
    raise AddressPointsUnavailable(
        "Register adries MV SR is not accessible. "
        "Options: (1) Download manually from minv.sk/?register-adries "
        "and place CSV in ingest/sources/register_adries_psk.csv, "
        "(2) Use INSPIRE WFS if available for your environment. "
        "Impact: Š1 and P-b will be INCOMPLETE for municipalities without address points."
    )


def _filter_and_format(
    points: list[dict],
    target_municipalities: dict,
) -> list[dict]:
    """Filter to target municipalities and format for DB insert."""
    filtered = []
    for p in points:
        muni_code = str(p.get("municipality_code", ""))
        muni_name = p.get("municipality_name", "")

        # Include if code matches OR name matches any target
        in_scope = (
            muni_code in target_municipalities
            or any(
                muni_name.lower() == name.lower()
                for name in target_municipalities.values()
            )
        )

        if not in_scope and not any(
            "presov" in muni_name.lower() or
            name.lower() in muni_name.lower()
            for name in target_municipalities.values()
        ):
            continue

        filtered.append({
            "municipality_code": muni_code,
            "street": p.get("street", ""),
            "house_number": p.get("house_number", ""),
            "postal_code": p.get("postal_code", ""),
            "geom": f"SRID=4326;POINT({p['lon']} {p['lat']})",
            "source_name": "Register adries MV SR",
            "source_date": "2024-01-01",
            # geometry_quality = 9 per DATA_INVENTORY_PSK.csv
        })

    return filtered


def _save_to_csv(points: list[dict]) -> None:
    """Save address points to local CSV cache."""
    if not points:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(points[0].keys())
    with open(CACHE_FILE_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(points)


def main() -> int:
    """Standalone runner."""
    validate_config()

    print("Loading address points (Register adries MV SR)...")
    try:
        points = load_address_points()
        print(f"Loaded {len(points)} address points")

        if points:
            result = upsert("address_points", points, on_conflict="geom")
            print(f"Inserted {result['inserted']} address points")
            if result["errors"]:
                for e in result["errors"][:3]:
                    print(f"ERROR: {e}", file=sys.stderr)
            return 0
    except AddressPointsUnavailable as e:
        print(f"\nBLOCKER: {e}", file=sys.stderr)
        print("\nIMPACT:", file=sys.stderr)
        print("  - Š1 (coverage check) = INCOMPLETE for municipalities without address points", file=sys.stderr)
        print("  - P-b (distance check) = INCOMPLETE for municipalities without address points", file=sys.stderr)
        print("\nTO UNBLOCK: Place address data file in:", file=sys.stderr)
        print(f"  {CACHE_FILE_CSV}", file=sys.stderr)
        print(f"  or {CACHE_FILE_GEOJSON}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
