"""
Fetch real OSM building footprints for the 21 shared municipalities (VZN
catchment neighbours of the 12 Prešov school districts, see
so_shared_municipality_areas) from OSM / Overpass (free) and store them in
skolske_obvody.osm_buildings.

Why: VLA-21 rendered each shared municipality's FULL cadastral polygon
(skolske_obvody.municipalities.geom) — fields, meadows and empty land
included. Client feedback (VLA-31): show only the actual inhabited area,
not the cadastral boundary. These municipalities are outside the school
district's own address-ingestion scope (house_geocodes/address_points are
empty for all 21 — verified live) and osm_street_lines only covers Prešov
city's own Overpass query. Named-street OSM tagging is also inconsistent
for small villages (Bzenov/Zlatá Baňa: 0 named highway ways) but building
footprints exist everywhere people live (294/329 buildings respectively,
verified live) — so buildings, not streets, are the universal real-data
signal used here.

The Overpass query is bbox-scoped from each municipality's OWN geom (already
disambiguated by VLA-21's nearest-candidate-to-home-municipality join in
so_shared_municipality_areas) — NOT Overpass's `area["name"=...]` matching,
which would silently resolve to the wrong place for any of the 16 duplicated
municipality names in this dataset (same trap VLA-21 already closed once).

Idempotent: truncates and re-loads skolske_obvody.osm_buildings each run.
NO paid API calls (Overpass is free; respects a polite User-Agent + delay).

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' .env.local | sed 's/^/export /')
    python3 ingest/fetch_osm_buildings.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
BBOX_PAD_DEG = 0.0015  # ~150m, catches buildings straddling the boundary
COURTESY_DELAY_S = 2


def fetch_municipalities() -> list[dict]:
    """The 21 shared municipalities already resolved by VLA-21's join, with a
    padded bbox derived from their own real geom (not name-matched)."""
    return query_sql(
        f"""
        SELECT m.id, m.name,
          public.ST_YMin(m.geom) - {BBOX_PAD_DEG} AS south,
          public.ST_XMin(m.geom) - {BBOX_PAD_DEG} AS west,
          public.ST_YMax(m.geom) + {BBOX_PAD_DEG} AS north,
          public.ST_XMax(m.geom) + {BBOX_PAD_DEG} AS east
        FROM skolske_obvody.municipalities m
        WHERE m.id IN (SELECT DISTINCT municipality_id FROM public.so_shared_municipality_areas)
        ORDER BY m.name
        """
    )


def fetch_overpass_buildings(south: float, west: float, north: float, east: float, label: str) -> list[dict]:
    """Fetch building ways within a bbox. Retries on transient errors."""
    query = (
        f"[out:json][timeout:60];way[\"building\"]({south},{west},{north},{east});out geom;"
    )
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                OVERPASS_URL,
                data=query.encode("utf-8"),
                headers={
                    "User-Agent": "skolske-obvody-44/1.0 (PSK VZN compliance)",
                    "Content-Type": "text/plain",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            els = data.get("elements", [])
            ways = [e for e in els if e.get("type") == "way" and e.get("geometry")]
            return ways
        except Exception as ex:  # noqa: BLE001
            last_err = ex
            wait = 5 * (attempt + 1)
            print(f"  [{label}] overpass error ({ex}); retry in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"[{label}] Overpass fetch failed after retries: {last_err}")


def way_to_wkt(way: dict) -> str | None:
    """Build an EWKT POLYGON from a closed building way's geometry nodes."""
    geom = way.get("geometry") or []
    pts = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
    if len(pts) < 4:
        return None
    if pts[0] != pts[-1]:
        pts.append(pts[0])  # close the ring
    coords = ", ".join(f"{lon} {lat}" for lon, lat in pts)
    return f"SRID=4326;POLYGON(({coords}))"


def ensure_table() -> None:
    print("\n[osm-buildings] Ensuring osm_buildings table...")
    r = exec_sql(
        """
        CREATE TABLE IF NOT EXISTS skolske_obvody.osm_buildings (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            municipality_id UUID NOT NULL,
            osm_way_id BIGINT,
            geom public.geometry(Polygon, 4326) NOT NULL,
            fetched_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    if not r.get("ok"):
        raise RuntimeError(f"create table failed: {r.get('message')}")
    r = exec_sql("TRUNCATE skolske_obvody.osm_buildings")
    if not r.get("ok"):
        raise RuntimeError(f"truncate failed: {r.get('message')}")
    exec_sql(
        "CREATE INDEX IF NOT EXISTS osm_buildings_gix "
        "ON skolske_obvody.osm_buildings USING GIST (geom)"
    )
    exec_sql(
        "CREATE INDEX IF NOT EXISTS osm_buildings_municipality_idx "
        "ON skolske_obvody.osm_buildings (municipality_id)"
    )
    print("  table ready (truncated)")


def load_buildings(municipality_id: str, ways: list[dict]) -> int:
    records = []
    for w in ways:
        wkt = way_to_wkt(w)
        if not wkt:
            continue
        records.append({"osm_way_id": w.get("id"), "geom": wkt})
    if not records:
        return 0
    inserted = 0
    BATCH = 200
    for i in range(0, len(records), BATCH):
        batch = records[i:i + BATCH]
        vals = []
        for rec in batch:
            wid = rec["osm_way_id"] if isinstance(rec["osm_way_id"], int) else "NULL"
            vals.append(
                f"($m${municipality_id}$m$, {wid}, public.ST_GeomFromEWKT($g${rec['geom']}$g$))"
            )
        sql = (
            "INSERT INTO skolske_obvody.osm_buildings (municipality_id, osm_way_id, geom) VALUES "
            + ",\n".join(vals)
        )
        r = exec_sql(sql)
        if not r.get("ok"):
            raise RuntimeError(f"insert batch failed: {r.get('message')}")
        inserted += len(batch)
    return inserted


def main() -> None:
    validate_config()
    print("=" * 64)
    print("Fetch OSM building footprints for 21 shared municipalities (free Overpass)")
    print("=" * 64)
    municipalities = fetch_municipalities()
    print(f"\n[osm-buildings] {len(municipalities)} municipalities to fetch")
    ensure_table()

    zero_building_municipalities = []
    total_inserted = 0
    for idx, m in enumerate(municipalities):
        label = m["name"]
        ways = fetch_overpass_buildings(m["south"], m["west"], m["north"], m["east"], label)
        n = load_buildings(m["id"], ways)
        total_inserted += n
        status = "OK" if n > 0 else "ZERO BUILDINGS"
        print(f"  [{idx + 1}/{len(municipalities)}] {label}: {n} buildings ({status})")
        if n == 0:
            zero_building_municipalities.append(label)
        if idx < len(municipalities) - 1:
            time.sleep(COURTESY_DELAY_S)

    print(f"\nDone. total_buildings={total_inserted}")
    if zero_building_municipalities:
        print(
            f"WARNING: {len(zero_building_municipalities)} municipalities returned ZERO "
            f"OSM buildings (no inhabited-area polygon will render for these): "
            f"{', '.join(zero_building_municipalities)}"
        )


if __name__ == "__main__":
    main()
