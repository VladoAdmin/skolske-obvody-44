"""
Fetch named street CENTERLINES for Prešov from OSM / Overpass (free) and store
them in skolske_obvody.street_geocodes-adjacent table `osm_street_lines`.

Why: the district geometry build needs continuous street geometry (lines), not
the single scattered POINT per street we currently have in street_geocodes.
Point-Voronoi on scattered points fragments districts; nearest-street-LINE
tessellation does not. road_network holds only unnamed major-road classes
(I/II/III triedy), so it cannot be attributed to VZN streets — OSM named ways
are the only free source of per-street centerlines that we can match by name to
the VZN street->district mapping.

This script is idempotent: it truncates and re-loads osm_street_lines each run.
NO paid API calls (Overpass is free; respects a polite User-Agent).

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/fetch_osm_streets.py
"""

from __future__ import annotations

import sys
import time
import urllib.request

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql, upsert

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """
[out:json][timeout:120];
area["name"="Prešov"]["admin_level"="8"]->.a;
way(area.a)["highway"]["name"];
out geom;
"""


def fetch_overpass() -> list[dict]:
    """Fetch named highway ways with full geometry. Retries on transient errors."""
    print("\n[osm] Fetching named street centerlines from Overpass (free)...")
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                OVERPASS_URL,
                data=OVERPASS_QUERY.encode("utf-8"),
                headers={
                    "User-Agent": "skolske-obvody-44/1.0 (PSK VZN compliance)",
                    "Content-Type": "text/plain",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=150) as resp:
                import json
                data = json.loads(resp.read().decode("utf-8"))
            els = data.get("elements", [])
            ways = [e for e in els if e.get("type") == "way" and e.get("geometry")]
            print(f"  fetched {len(ways)} named ways")
            return ways
        except Exception as ex:  # noqa: BLE001
            last_err = ex
            wait = 5 * (attempt + 1)
            print(f"  overpass error ({ex}); retry in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"Overpass fetch failed after retries: {last_err}")


def way_to_wkt(way: dict) -> str | None:
    """Build an EWKT LINESTRING from an Overpass way's geometry nodes."""
    geom = way.get("geometry") or []
    pts = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
    if len(pts) < 2:
        return None
    coords = ", ".join(f"{lon} {lat}" for lon, lat in pts)
    return f"SRID=4326;LINESTRING({coords})"


def ensure_table() -> None:
    print("\n[osm] Ensuring osm_street_lines table...")
    r = exec_sql(
        """
        CREATE TABLE IF NOT EXISTS skolske_obvody.osm_street_lines (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL,
            osm_way_id BIGINT,
            geom public.geometry(LineString, 4326) NOT NULL,
            fetched_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    if not r.get("ok"):
        raise RuntimeError(f"create table failed: {r.get('message')}")
    r = exec_sql("TRUNCATE skolske_obvody.osm_street_lines")
    if not r.get("ok"):
        raise RuntimeError(f"truncate failed: {r.get('message')}")
    exec_sql(
        "CREATE INDEX IF NOT EXISTS osm_street_lines_gix "
        "ON skolske_obvody.osm_street_lines USING GIST (geom)"
    )
    exec_sql(
        "CREATE INDEX IF NOT EXISTS osm_street_lines_name_idx "
        "ON skolske_obvody.osm_street_lines (name)"
    )
    print("  table ready (truncated)")


def load_lines(ways: list[dict]) -> int:
    records = []
    skipped = 0
    for w in ways:
        name = (w.get("tags") or {}).get("name")
        wkt = way_to_wkt(w)
        if not name or not wkt:
            skipped += 1
            continue
        records.append({"name": name, "osm_way_id": w.get("id"), "geom": wkt})
    print(f"\n[osm] Loading {len(records)} line segments ({skipped} skipped)...")
    # geom column is not in supabase_client._GEOM_COLUMNS by default; it IS named
    # 'geom' so the client renders it via ST_GeomFromEWKT. Insert in batches.
    inserted = 0
    BATCH = 100
    for i in range(0, len(records), BATCH):
        batch = records[i:i + BATCH]
        vals = []
        for rec in batch:
            nm = rec["name"].replace("$", "")
            wid = rec["osm_way_id"] if rec["osm_way_id"] is not None else "NULL"
            vals.append(
                f"($n${nm}$n$, {wid}, public.ST_GeomFromEWKT($g${rec['geom']}$g$))"
            )
        sql = (
            "INSERT INTO skolske_obvody.osm_street_lines (name, osm_way_id, geom) VALUES "
            + ",\n".join(vals)
        )
        r = exec_sql(sql)
        if not r.get("ok"):
            raise RuntimeError(f"insert batch failed: {r.get('message')}")
        inserted += len(batch)
    print(f"  inserted {inserted} segments")
    return inserted


def main() -> None:
    validate_config()
    print("=" * 64)
    print("Fetch OSM street centerlines for Prešov (free Overpass)")
    print("=" * 64)
    ways = fetch_overpass()
    ensure_table()
    n = load_lines(ways)
    rows = query_sql(
        "SELECT count(*) AS segs, count(DISTINCT name) AS names "
        "FROM skolske_obvody.osm_street_lines"
    )
    print(f"\nDone. segments={rows[0]['segs']} distinct_names={rows[0]['names']}")


if __name__ == "__main__":
    main()
