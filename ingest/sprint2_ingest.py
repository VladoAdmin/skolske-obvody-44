"""
Sprint 2 Ingest — three gap-filling tasks for skolske_obvody.

TASK 1: Filter schools to MŠ + ZŠ only (delete ZUŠ, OTHER).
TASK 2: Add 5 supporting dataset tables (DDL + WFS load).
TASK 3: Derive district geometry from SK OSM PBF.
POST:   Topology checks T1/T2/T3 + OSRM walking-distance demo.

Run:
    export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
    cd projects/skolske-obvody-44
    python3 -m ingest.sprint2_ingest
"""

import json
import sys
import time
import uuid
from datetime import date
from typing import Optional

import requests

from ingest.config import (
    WFS_LAYER_MRK_ATLAS,
    WFS_LAYER_MRK_VARHANOVCE,
    WFS_LAYER_MRK_OSTROVANY,
    WFS_LAYER_MRK_KRIVANY,
    WFS_LAYER_MRK_DLHE_STRAZE,
    WFS_LAYER_MRK_VARADKA,
    WFS_LAYER_MRK_CICAVA,
    WFS_LAYER_PAD_BUS_STOPS,
    WFS_LAYER_RAIL_STOPS,
    WFS_LAYER_ROADS_I,
    WFS_LAYER_ROADS_II,
    WFS_LAYER_ROADS_III,
    WFS_LAYER_CHILDREN_0_14,
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    validate_config,
    WFS_SOURCE_DATE,
)
from ingest.supabase_client import exec_sql, query_sql, count, upsert
from ingest.wfs_connector import fetch_wfs_layer, geojson_to_wkt, WFSError

OSRM_URL = "http://osrm-sk:5000"
TODAY = date.today().isoformat()
SCHEMA = "skolske_obvody"

BLOCKER_LOG: list[dict] = []
SUMMARY: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blocker(source: str, reason: str) -> None:
    BLOCKER_LOG.append({"source": source, "reason": reason})
    print(f"  BLOCKER [{source}]: {reason}", file=sys.stderr)


def _section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


def _to_ewkt_multipolygon(wkt: str) -> str:
    upper = wkt.upper().strip()
    if upper.startswith("MULTIPOLYGON"):
        return f"SRID=4326;{wkt}"
    if upper.startswith("POLYGON"):
        inner = wkt[wkt.index("("):]
        return f"SRID=4326;MULTIPOLYGON({inner})"
    return f"SRID=4326;{wkt}"


def _to_ewkt_point(wkt: str) -> str:
    return f"SRID=4326;{wkt}"


def _to_ewkt_linestring(wkt: str) -> str:
    upper = wkt.upper().strip()
    if upper.startswith("MULTILINESTRING"):
        # Take first component as LineString for road_network
        # Keep as-is but wrap appropriately
        return f"SRID=4326;{wkt}"
    return f"SRID=4326;{wkt}"


# ---------------------------------------------------------------------------
# TASK 1 — Filter schools to MŠ + ZŠ only
# ---------------------------------------------------------------------------

def task1_filter_schools() -> None:
    _section("TASK 1: Filter schools to MŠ + ZŠ only")

    # Current counts by type
    rows = query_sql(
        "SELECT type, COUNT(*) as n FROM skolske_obvody.schools GROUP BY type ORDER BY n DESC"
    )
    print("  Current school types:")
    total_before = 0
    for r in rows:
        print(f"    {r['type']}: {r['n']}")
        total_before += int(r['n'])
    print(f"  Total before: {total_before}")

    # Delete all rows that are not ZS or MS
    result = exec_sql(
        "DELETE FROM skolske_obvody.schools WHERE type NOT IN ('ZS', 'MS')"
    )
    if not result.get("ok"):
        _blocker(
            "task1_filter_schools",
            f"DELETE failed: {result.get('message', 'unknown')}",
        )
        return

    total_after = count("schools")
    SUMMARY["task1_schools"] = {
        "before": total_before,
        "after": total_after,
        "deleted": total_before - total_after,
    }
    print(f"  Deleted {total_before - total_after} non-ZS/MS rows")
    print(f"  Remaining: {total_after} schools (ZS + MS only)")

    # Verify type distribution
    rows2 = query_sql(
        "SELECT type, COUNT(*) as n FROM skolske_obvody.schools GROUP BY type ORDER BY n DESC"
    )
    for r in rows2:
        print(f"    {r['type']}: {r['n']}")


# ---------------------------------------------------------------------------
# TASK 2 — DDL for 5 new tables
# ---------------------------------------------------------------------------

DDL_MRK_ATLAS = """
CREATE TABLE IF NOT EXISTS skolske_obvody.mrk_atlas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    obec_id     UUID REFERENCES skolske_obvody.municipalities(id) ON DELETE SET NULL,
    obec_name   TEXT,
    category    TEXT,
    geom        public.geometry(MultiPolygon, 4326),
    provenance  JSONB
);
ALTER TABLE skolske_obvody.mrk_atlas DISABLE ROW LEVEL SECURITY;
GRANT SELECT ON skolske_obvody.mrk_atlas TO authenticated;
"""

DDL_MRK_BUILDINGS = """
CREATE TABLE IF NOT EXISTS skolske_obvody.mrk_buildings (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    obec    TEXT NOT NULL,
    geom    public.geometry(Point, 4326) NOT NULL,
    provenance JSONB
);
ALTER TABLE skolske_obvody.mrk_buildings DISABLE ROW LEVEL SECURITY;
GRANT SELECT ON skolske_obvody.mrk_buildings TO authenticated;
"""

DDL_TRANSIT_STOPS = """
CREATE TABLE IF NOT EXISTS skolske_obvody.transit_stops (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind    TEXT CHECK (kind IN ('bus', 'rail')),
    name    TEXT,
    geom    public.geometry(Point, 4326) NOT NULL,
    provenance JSONB
);
ALTER TABLE skolske_obvody.transit_stops DISABLE ROW LEVEL SECURITY;
GRANT SELECT ON skolske_obvody.transit_stops TO authenticated;
"""

DDL_ROAD_NETWORK = """
CREATE TABLE IF NOT EXISTS skolske_obvody.road_network (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class   TEXT CHECK (class IN ('I', 'II', 'III')),
    geom    public.geometry(LineString, 4326) NOT NULL,
    provenance JSONB
);
ALTER TABLE skolske_obvody.road_network DISABLE ROW LEVEL SECURITY;
GRANT SELECT ON skolske_obvody.road_network TO authenticated;
"""

DDL_DEMOGRAPHICS = """
CREATE TABLE IF NOT EXISTS skolske_obvody.demographics_children (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    municipality_id UUID NOT NULL REFERENCES skolske_obvody.municipalities(id),
    count           INTEGER NOT NULL,
    year            INTEGER,
    provenance      JSONB
);
ALTER TABLE skolske_obvody.demographics_children DISABLE ROW LEVEL SECURITY;
GRANT SELECT ON skolske_obvody.demographics_children TO authenticated;
"""


def task2_create_tables() -> None:
    _section("TASK 2a: Create 5 new tables via DDL")
    tables_ddl = [
        ("mrk_atlas", DDL_MRK_ATLAS),
        ("mrk_buildings", DDL_MRK_BUILDINGS),
        ("transit_stops", DDL_TRANSIT_STOPS),
        ("road_network", DDL_ROAD_NETWORK),
        ("demographics_children", DDL_DEMOGRAPHICS),
    ]
    for name, ddl in tables_ddl:
        # Execute each statement separately (DDL + GRANT)
        stmts = [s.strip() for s in ddl.strip().split(";") if s.strip()]
        ok = True
        for stmt in stmts:
            r = exec_sql(stmt)
            if not r.get("ok"):
                _blocker(f"ddl_{name}", f"DDL failed: {r.get('message','?')}")
                ok = False
                break
        if ok:
            print(f"  OK: {name} created/verified")


# ---------------------------------------------------------------------------
# TASK 2 — Load data into 5 new tables
# ---------------------------------------------------------------------------

def _get_muni_map() -> dict[str, str]:
    """Return {code: uuid} for all municipalities."""
    rows = query_sql("SELECT id, code FROM skolske_obvody.municipalities LIMIT 2000")
    return {r["code"]: r["id"] for r in rows}


def load_mrk_atlas(muni_map: dict[str, str]) -> None:
    _section("TASK 2b: Load mrk_atlas (~224)")
    try:
        features = fetch_wfs_layer(WFS_LAYER_MRK_ATLAS, max_features=500)
    except WFSError as e:
        _blocker("mrk_atlas", str(e))
        return

    records = []
    for f in features:
        props = f["properties"]
        idn4 = str(props.get("IDN4", ""))
        nm4 = props.get("NM4", "")
        # category: use poc_2019 tier or presence indicator
        poc = props.get("poc_2019", 0) or 0
        if poc > 500:
            cat = "large"
        elif poc > 100:
            cat = "medium"
        elif poc > 0:
            cat = "small"
        else:
            cat = "unknown"

        wkt = geojson_to_wkt(f)
        if not wkt:
            continue

        obec_uuid = muni_map.get(idn4)
        rec = {
            "obec_id": obec_uuid,
            "obec_name": nm4,
            "category": cat,
            "geom": _to_ewkt_multipolygon(wkt),
            "provenance": json.dumps({
                "source": "geo-psk:wm_ark_municipal",
                "layer": "Atlas rómskych komunít 2019",
                "fetched_at": TODAY,
            }),
        }
        records.append(rec)

    if not records:
        _blocker("mrk_atlas", "No features with geometry")
        return

    # Truncate first for clean reload
    exec_sql("TRUNCATE TABLE skolske_obvody.mrk_atlas")
    result = upsert("mrk_atlas", records, on_conflict="id")
    n = count("mrk_atlas")
    SUMMARY["mrk_atlas"] = {"inserted": n}
    print(f"  Inserted: {n} rows")
    if result["errors"]:
        print(f"  Errors: {len(result['errors'])} batches failed")
        for e in result["errors"][:2]:
            print(f"    {e}", file=sys.stderr)


def load_mrk_buildings() -> None:
    _section("TASK 2c: Load mrk_buildings (6 MRK obcí, ~3198 expected)")
    layers = [
        (WFS_LAYER_MRK_VARHANOVCE, "Varhaňovce"),
        (WFS_LAYER_MRK_OSTROVANY, "Ostrovany"),
        (WFS_LAYER_MRK_KRIVANY, "Krivany"),
        (WFS_LAYER_MRK_DLHE_STRAZE, "Dlhé Stráže"),
        (WFS_LAYER_MRK_VARADKA, "Varadka"),
        (WFS_LAYER_MRK_CICAVA, "Čičava"),
    ]

    all_records = []
    for layer_name, obec in layers:
        try:
            features = fetch_wfs_layer(layer_name, max_features=5000)
        except WFSError as e:
            _blocker(f"mrk_buildings_{obec}", str(e))
            continue

        count_layer = 0
        for f in features:
            wkt = geojson_to_wkt(f)
            if not wkt:
                continue
            # Centroids for Polygon buildings → Point
            # Use shapely to get centroid
            try:
                from shapely.geometry import shape
                geom_shape = shape(f["geometry"])
                cx, cy = geom_shape.centroid.x, geom_shape.centroid.y
                point_wkt = f"POINT({cx} {cy})"
            except Exception:
                # fallback: use wkt as-is if it's already a point
                point_wkt = wkt

            rec = {
                "obec": obec,
                "geom": _to_ewkt_point(point_wkt),
                "provenance": json.dumps({
                    "source": layer_name,
                    "fetched_at": TODAY,
                }),
            }
            all_records.append(rec)
            count_layer += 1
        print(f"    {obec}: {count_layer} buildings")

    if not all_records:
        _blocker("mrk_buildings", "No records across all 6 layers")
        return

    exec_sql("TRUNCATE TABLE skolske_obvody.mrk_buildings")
    result = upsert("mrk_buildings", all_records, on_conflict="id", batch_size=300)
    n = count("mrk_buildings")
    SUMMARY["mrk_buildings"] = {"inserted": n}
    print(f"  Total inserted: {n} rows")
    if result["errors"]:
        print(f"  Errors: {len(result['errors'])} batches", file=sys.stderr)


def load_transit_stops() -> None:
    _section("TASK 2d: Load transit_stops (bus PAD + rail, ~3299 expected)")
    exec_sql("TRUNCATE TABLE skolske_obvody.transit_stops")

    # Bus stops
    total_bus = 0
    try:
        features = fetch_wfs_layer(WFS_LAYER_PAD_BUS_STOPS, max_features=5000)
        records = []
        for f in features:
            props = f["properties"]
            wkt = geojson_to_wkt(f)
            if not wkt:
                continue
            records.append({
                "kind": "bus",
                "name": props.get("Name", ""),
                "geom": _to_ewkt_point(wkt),
                "provenance": json.dumps({
                    "source": WFS_LAYER_PAD_BUS_STOPS,
                    "fetched_at": TODAY,
                }),
            })
        result = upsert("transit_stops", records, on_conflict="id", batch_size=300)
        total_bus = count("transit_stops")
        print(f"  Bus stops inserted: {total_bus}")
        if result["errors"]:
            print(f"  Bus errors: {len(result['errors'])} batches", file=sys.stderr)
    except WFSError as e:
        _blocker("transit_stops_bus", str(e))

    # Rail stops
    total_rail_added = 0
    try:
        features = fetch_wfs_layer(WFS_LAYER_RAIL_STOPS, max_features=500)
        records = []
        for f in features:
            props = f["properties"]
            wkt = geojson_to_wkt(f)
            if not wkt:
                continue
            records.append({
                "kind": "rail",
                "name": props.get("stop_name", ""),
                "geom": _to_ewkt_point(wkt),
                "provenance": json.dumps({
                    "source": WFS_LAYER_RAIL_STOPS,
                    "fetched_at": TODAY,
                }),
            })
        result = upsert("transit_stops", records, on_conflict="id", batch_size=300)
        n_after = count("transit_stops")
        total_rail_added = n_after - total_bus
        print(f"  Rail stops inserted: {total_rail_added}")
        if result["errors"]:
            print(f"  Rail errors: {len(result['errors'])} batches", file=sys.stderr)
    except WFSError as e:
        _blocker("transit_stops_rail", str(e))

    n_total = count("transit_stops")
    SUMMARY["transit_stops"] = {"inserted": n_total, "bus": total_bus, "rail": total_rail_added}
    print(f"  Total transit_stops: {n_total}")


def load_road_network() -> None:
    _section("TASK 2e: Load road_network (I+II+III, ~428 segments)")
    exec_sql("TRUNCATE TABLE skolske_obvody.road_network")

    from shapely.geometry import shape, LineString as SLS
    from shapely.ops import linemerge
    from shapely.wkt import dumps as wkt_dumps

    road_layers = [
        (WFS_LAYER_ROADS_I, "I"),
        (WFS_LAYER_ROADS_II, "II"),
        (WFS_LAYER_ROADS_III, "III"),
    ]
    total = 0
    for layer_name, cls in road_layers:
        try:
            features = fetch_wfs_layer(layer_name, max_features=2000)
        except WFSError as e:
            _blocker(f"road_network_{cls}", str(e))
            continue

        records = []
        for f in features:
            s = shape(f["geometry"])
            # Expand MultiLineString into individual 2D LineStrings
            if s.geom_type == "MultiLineString":
                merged = linemerge(s)
                components = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
            elif s.geom_type == "LineString":
                components = [s]
            else:
                continue

            for component in components:
                if component.geom_type != "LineString" or len(component.coords) < 2:
                    continue
                # Force 2D — strip Z coordinate
                coords_2d = [(c[0], c[1]) for c in component.coords]
                ls2d = SLS(coords_2d)
                wkt_2d = wkt_dumps(ls2d, rounding_precision=7)
                records.append({
                    "class": cls,
                    "geom": f"SRID=4326;{wkt_2d}",
                    "provenance": json.dumps({
                        "source": layer_name,
                        "class": cls,
                        "fetched_at": TODAY,
                    }),
                })

        if records:
            result = upsert("road_network", records, on_conflict="id", batch_size=100)
            n = count("road_network")
            added = n - total
            total = n
            print(f"  Class {cls}: {added} segments from {len(features)} features (total: {n})")
            if result["errors"]:
                print(f"  Errors: {len(result['errors'])} batches", file=sys.stderr)
                for e in result["errors"][:2]:
                    print(f"    {e}", file=sys.stderr)

    SUMMARY["road_network"] = {"inserted": total}
    print(f"  Total road_network: {total} rows")


def load_demographics_children(muni_map: dict[str, str]) -> None:
    _section("TASK 2f: Load demographics_children (665 municipalities)")
    try:
        features = fetch_wfs_layer(WFS_LAYER_CHILDREN_0_14, max_features=1000)
    except WFSError as e:
        _blocker("demographics_children", str(e))
        return

    # NUTS code → municipality code (last 6 chars)
    records = []
    unmatched = 0
    for f in features:
        props = f["properties"]
        nuts = props.get("nuts", "")
        muni_code = nuts[-6:] if len(nuts) >= 6 else ""
        muni_uuid = muni_map.get(muni_code)
        if not muni_uuid:
            unmatched += 1
            continue

        # Use _last column (most recent) or fall back to _2020
        count_val = props.get("_last") or props.get("_2020")
        if count_val is None:
            unmatched += 1
            continue

        # Year: find highest year with non-null data
        year = 2020
        for yr in range(2020, 1995, -1):
            if props.get(f"_{yr}") is not None:
                year = yr
                break

        records.append({
            "municipality_id": muni_uuid,
            "count": int(count_val),
            "year": year,
            "provenance": json.dumps({
                "source": WFS_LAYER_CHILDREN_0_14,
                "indicator": props.get("ukaz", "IN010053"),
                "fetched_at": TODAY,
            }),
        })

    if unmatched:
        print(f"  WARNING: {unmatched} rows skipped (no municipality match)")

    if not records:
        _blocker("demographics_children", "No records could be matched to municipalities")
        return

    exec_sql("TRUNCATE TABLE skolske_obvody.demographics_children")
    result = upsert("demographics_children", records, on_conflict="id", batch_size=300)
    n = count("demographics_children")
    SUMMARY["demographics_children"] = {"inserted": n, "unmatched": unmatched}
    print(f"  Inserted: {n} rows")
    if result["errors"]:
        print(f"  Errors: {len(result['errors'])} batches", file=sys.stderr)


# ---------------------------------------------------------------------------
# TASK 3 — Derive district geometry from SK OSM PBF
# ---------------------------------------------------------------------------

OSM_PBF_PATH = "/host-opt/frantiska-2/osrm-sk/slovakia-latest.osm.pbf"

# Prešov bbox (from municipalities query)
PRESOV_BBOX = (21.156965, 48.945021, 21.335406, 49.046839)


def _extract_presov_streets(pbf_path: str, bbox: tuple) -> dict[str, list]:
    """
    Extract named highway ways within Prešov bbox from OSM PBF.
    Returns {street_name_lower: [list of WKT LineString]}.

    Uses pyosmium. Coordinates in WGS-84 (the PBF is in WGS-84).
    """
    import osmium

    minx, miny, maxx, maxy = bbox
    streets: dict[str, list] = {}  # name_lower → [[(lon,lat), ...], ...]

    class StreetHandler(osmium.SimpleHandler):
        def way(self, w):
            tags = {t.k: t.v for t in w.tags}
            highway = tags.get("highway")
            name = tags.get("name", "").strip()
            if not highway or not name:
                return
            # Only named road types (no footway-only for district matching)
            if highway in ("footway", "path", "steps", "cycleway", "track"):
                return
            try:
                coords = [(n.lon, n.lat) for n in w.nodes]
            except osmium.InvalidLocationError:
                return
            if not coords:
                return
            # Check bbox overlap
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            if max(lons) < minx or min(lons) > maxx:
                return
            if max(lats) < miny or min(lats) > maxy:
                return

            name_lower = name.lower()
            if name_lower not in streets:
                streets[name_lower] = []
            streets[name_lower].append(coords)

    handler = StreetHandler()
    print(f"  Parsing OSM PBF: {pbf_path} ...")
    handler.apply_file(pbf_path, locations=True)
    print(f"  Extracted {len(streets)} distinct street names in Prešov bbox")
    return streets


def _coords_to_linestring_wkt(coords: list) -> str:
    """Convert list of (lon, lat) to WKT LINESTRING."""
    pts = " ".join(f"{lon} {lat}" for lon, lat in coords)
    return f"LINESTRING({pts})"


def _build_district_geom(street_names: list[str], osm_streets: dict) -> tuple[Optional[str], list[str]]:
    """
    For a district's street list, find matching OSM ways, buffer + hull.
    Returns (EWKT_MULTIPOLYGON or None, list_of_unresolved_street_names).
    """
    from shapely.geometry import MultiLineString, MultiPolygon
    from shapely.ops import unary_union

    matched_lines = []
    unresolved = []

    for sname in street_names:
        sname_lower = sname.lower().strip()
        ways = osm_streets.get(sname_lower)
        if ways:
            for coord_list in ways:
                if len(coord_list) >= 2:
                    matched_lines.append(coord_list)
        else:
            # Fuzzy: try removing diacritics / prefix match
            found = False
            for osm_key in osm_streets:
                if sname_lower in osm_key or osm_key in sname_lower:
                    for coord_list in osm_streets[osm_key]:
                        if len(coord_list) >= 2:
                            matched_lines.append(coord_list)
                    found = True
                    break
            if not found:
                unresolved.append(sname)

    if not matched_lines:
        return None, unresolved

    # Build shapely MultiLineString
    from shapely.geometry import LineString
    lines = [LineString(coords) for coords in matched_lines]
    multi = unary_union(lines)

    # Buffer 50m ≈ 0.00045° latitude (rough)
    buffered = multi.buffer(0.00045)

    # Convex hull → MultiPolygon
    hull = buffered.convex_hull
    if hull.geom_type == "Polygon":
        hull = MultiPolygon([hull])
    elif hull.geom_type != "MultiPolygon":
        hull = hull.convex_hull
        if hull.geom_type == "Polygon":
            hull = MultiPolygon([hull])

    if hull.is_empty or hull.area == 0:
        return None, unresolved

    from shapely.wkt import dumps as wkt_dumps
    wkt = wkt_dumps(hull, rounding_precision=7)
    ewkt = _to_ewkt_multipolygon(wkt)
    return ewkt, unresolved


def task3_derive_district_geometry() -> None:
    _section("TASK 3: Derive district geometry from OSM PBF")

    # Load all districts with street lists
    districts = query_sql(
        "SELECT id, name, metadata FROM skolske_obvody.districts"
    )
    if not districts:
        _blocker("task3_geometry", "No districts found")
        return

    print(f"  Found {len(districts)} districts")

    # Extract Prešov streets from PBF
    try:
        osm_streets = _extract_presov_streets(OSM_PBF_PATH, PRESOV_BBOX)
    except Exception as e:
        _blocker("task3_osm_extract", f"OSM extraction failed: {e}")
        return

    if not osm_streets:
        _blocker("task3_osm_extract", "No streets extracted from OSM PBF")
        return

    # Process each district
    updated = 0
    failed = 0

    for d in districts:
        district_id = d["id"]
        name = d["name"]
        meta = d.get("metadata") or {}
        streets = meta.get("streets", [])

        if not streets:
            print(f"  SKIP [{name[:40]}]: no streets in metadata")
            failed += 1
            continue

        ewkt, unresolved = _build_district_geom(streets, osm_streets)

        # Build updated metadata
        meta["geom_method"] = "osm_street_buffer_hull"
        if unresolved:
            meta["unresolved_streets"] = unresolved

        meta_json = json.dumps(meta, ensure_ascii=False)

        if ewkt:
            sql = f"""
UPDATE skolske_obvody.districts
SET
    geom = public.ST_GeomFromEWKT($_geom${ewkt}$_geom$),
    geometry_quality = 5,
    geometry_confidence = 'low',
    metadata = $_meta${meta_json}$_meta$::jsonb
WHERE id = '{district_id}'
"""
            r = exec_sql(sql)
            if r.get("ok"):
                n_matched = len(streets) - len(unresolved)
                print(
                    f"  OK [{name[:45]}]: {n_matched}/{len(streets)} streets matched, "
                    f"{len(unresolved)} unresolved"
                )
                updated += 1
            else:
                print(f"  ERROR [{name[:40]}]: {r.get('message', '?')}", file=sys.stderr)
                failed += 1
        else:
            # Update metadata with unresolved info even if no geom
            sql = f"""
UPDATE skolske_obvody.districts
SET metadata = $_meta${meta_json}$_meta$::jsonb
WHERE id = '{district_id}'
"""
            exec_sql(sql)
            print(f"  NO GEOM [{name[:40]}]: {len(streets)} streets, all unresolved")
            failed += 1

    SUMMARY["task3_geometry"] = {"updated": updated, "failed": failed}
    print(f"\n  Districts with geom: {updated}/{len(districts)}")
    print(f"  Districts without geom: {failed}/{len(districts)}")


# ---------------------------------------------------------------------------
# School FK linking via Nominatim geocoding
# ---------------------------------------------------------------------------

def _nominatim_geocode(address: str, city: str = "Prešov") -> tuple:
    """Geocode an address string via Nominatim. Returns (lon, lat) or (None, None)."""
    import urllib.parse as _up
    q = _up.urlencode({
        "q": f"{address}, {city}, Slovakia",
        "format": "json",
        "limit": 1,
    })
    url = f"https://nominatim.openstreetmap.org/search?{q}"
    req = __import__("urllib.request", fromlist=["Request", "urlopen"]).Request(
        url, headers={"User-Agent": "SkolskeOvbody-Ingest/1.0"}
    )
    try:
        import urllib.request as _ur
        with _ur.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data:
            return float(data[0]["lon"]), float(data[0]["lat"])
    except Exception as e:
        print(f"  Nominatim error for {address!r}: {e}", file=sys.stderr)
    return None, None


def link_district_schools() -> None:
    """
    Link each district to a school record using geocoded address.
    Strategy: geocode metadata.school_address, find nearest school in DB.
    If no school in DB within 500m, store geocoded point in metadata for demo use.
    """
    _section("TASK 3b: Link districts to schools via geocoding")
    districts = query_sql(
        "SELECT id, name, school_type, metadata FROM skolske_obvody.districts ORDER BY name"
    )

    linked = 0
    geocoded_only = 0
    failed = 0

    for d in districts:
        meta = d.get("metadata") or {}
        addr = meta.get("school_address", "")
        if not addr:
            failed += 1
            continue

        lon, lat = _nominatim_geocode(addr)
        time.sleep(0.4)  # Nominatim rate limit: 1 req/s

        if lon is None:
            print(f"  NO_GEOCODE [{d['name'][:45]}]")
            failed += 1
            continue

        # Store geocoded position in metadata regardless
        meta["school_geocoded_lon"] = lon
        meta["school_geocoded_lat"] = lat

        # Find nearest school within 300m in DB
        nearest = query_sql(f"""
SELECT id, name,
       public.ST_Distance(
           public.ST_SetSRID(public.ST_MakePoint({lon}, {lat}), 4326)::public.geography,
           geom::public.geography
       ) AS dist_m
FROM skolske_obvody.schools
WHERE public.ST_DWithin(
    public.ST_SetSRID(public.ST_MakePoint({lon}, {lat}), 4326)::public.geography,
    geom::public.geography,
    300
)
ORDER BY dist_m
LIMIT 1
""")

        school_id_val = "NULL"
        if nearest:
            school_id_val = f"'{nearest[0]['id']}'"
            dist_m = nearest[0]["dist_m"]
            print(f"  FK [{d['name'][:40]}] → {nearest[0]['name'][:35]} ({dist_m:.0f}m)")
            linked += 1
        else:
            print(f"  GEOCODED_ONLY [{d['name'][:40]}] → lon={lon:.4f},lat={lat:.4f} (no DB school within 300m)")
            geocoded_only += 1

        meta_json = json.dumps(meta, ensure_ascii=False)
        sql = f"""
UPDATE skolske_obvody.districts
SET school_id = {school_id_val},
    metadata = $_meta${meta_json}$_meta$::jsonb
WHERE id = '{d["id"]}'
"""
        r = exec_sql(sql)
        if not r.get("ok"):
            print(f"  UPDATE ERROR: {r.get('message', '?')}", file=sys.stderr)

    SUMMARY["school_fk_linked"] = linked
    SUMMARY["school_geocoded_only"] = geocoded_only
    print(f"\n  Linked to DB school: {linked}, geocoded-only: {geocoded_only}, failed: {failed}")


# ---------------------------------------------------------------------------
# TOPOLOGY CHECKS
# ---------------------------------------------------------------------------

def topology_checks() -> None:
    _section("TOPOLOGY CHECKS T1 / T2 / T3")

    # T1: ST_IsValid for all district geoms
    print("\nT1 — ST_IsValid per district:")
    rows = query_sql(
        "SELECT name, public.ST_IsValid(geom) as valid, "
        "geom IS NOT NULL as has_geom "
        "FROM skolske_obvody.districts ORDER BY name"
    )
    valid_count = sum(1 for r in rows if r.get("valid"))
    geom_count = sum(1 for r in rows if r.get("has_geom"))
    for r in rows:
        status = "VALID" if r.get("valid") else ("NULL" if not r.get("has_geom") else "INVALID")
        print(f"  [{status}] {r['name'][:55]}")
    print(f"  → {geom_count} with geom, {valid_count} pass ST_IsValid")
    SUMMARY["T1_valid"] = valid_count
    SUMMARY["T1_geom_count"] = geom_count

    # T2: Overlaps between districts of same school_type + teaching_language
    print("\nT2 — Overlaps between same-type districts:")
    rows2 = query_sql("""
SELECT
    a.name AS a_name,
    b.name AS b_name,
    public.ST_Area(public.ST_Intersection(a.geom, b.geom)) AS overlap_area
FROM skolske_obvody.districts a
JOIN skolske_obvody.districts b ON a.id < b.id
    AND a.school_type = b.school_type
    AND a.teaching_language = b.teaching_language
    AND a.geom IS NOT NULL
    AND b.geom IS NOT NULL
    AND public.ST_Overlaps(a.geom, b.geom)
""")
    if rows2:
        print(f"  NOTE: {len(rows2)} overlapping district pairs (expected for coarse OSM-buffer geometry):")
        for r in rows2[:5]:
            print(f"    {r['a_name'][:35]} ↔ {r['b_name'][:35]} (area~{r.get('overlap_area', 0):.4f}°²)")
    else:
        print("  OK: No overlaps between same-type+language districts")
    SUMMARY["T2_overlaps"] = len(rows2)

    # T3: Each district's school FK + school proximity
    print("\nT3 — School FK and proximity check:")
    # Use geocoded lon/lat from metadata for districts without DB school FK
    rows3 = query_sql("""
SELECT
    d.name AS district_name,
    d.school_type,
    d.school_id IS NOT NULL AS has_school_fk,
    d.geom IS NOT NULL AS has_geom,
    (d.metadata->>'school_geocoded_lon') AS school_lon,
    (d.metadata->>'school_geocoded_lat') AS school_lat,
    public.ST_X(public.ST_Centroid(d.geom)) AS d_lon,
    public.ST_Y(public.ST_Centroid(d.geom)) AS d_lat
FROM skolske_obvody.districts d
ORDER BY d.name
""")
    t3_fk = sum(1 for r in rows3 if r.get("has_school_fk"))
    t3_geocoded = sum(1 for r in rows3 if r.get("school_lon"))
    for r in rows3:
        fk = "FK_DB" if r.get("has_school_fk") else ("GEOCODED" if r.get("school_lon") else "NO_SCHOOL")
        print(f"  [{fk}] {r['district_name'][:55]}")
    print(f"  → Districts with DB school FK: {t3_fk}/{len(rows3)}")
    print(f"  → Districts with geocoded school pos: {t3_geocoded}/{len(rows3)}")
    SUMMARY["T3_fk_count"] = t3_fk
    SUMMARY["T3_geocoded_count"] = t3_geocoded


# ---------------------------------------------------------------------------
# WALKING DISTANCE DEMO
# ---------------------------------------------------------------------------

def osrm_walking_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> Optional[float]:
    """Return walking distance in meters via OSRM, or None on failure."""
    url = f"{OSRM_URL}/route/v1/walking/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("code") == "Ok":
            return data["routes"][0]["distance"]
    except Exception as e:
        print(f"  OSRM error: {e}", file=sys.stderr)
    return None


def walking_distance_demo() -> None:
    _section("WALKING DISTANCE DEMO (5 districts × OSRM)")

    # Get districts with geom and geocoded school position
    rows = query_sql("""
SELECT
    d.name AS district_name,
    d.school_type,
    public.ST_X(public.ST_Centroid(d.geom)) AS d_lon,
    public.ST_Y(public.ST_Centroid(d.geom)) AS d_lat,
    (d.metadata->>'school_geocoded_lon')::float AS s_lon,
    (d.metadata->>'school_geocoded_lat')::float AS s_lat
FROM skolske_obvody.districts d
WHERE d.geom IS NOT NULL
    AND d.metadata->>'school_geocoded_lon' IS NOT NULL
ORDER BY d.name
LIMIT 5
""")

    if not rows:
        print("  No districts with geom + geocoded school. Cannot run demo.")
        _blocker("walking_demo", "No geocoded school positions available")
        return

    print(f"\n  Testing {len(rows)} district-centroid → geocoded-school routes:")
    print(f"\n  {'District':<45} {'Type':<5} {'Dist(m)':>8} {'Threshold':>10} {'§44 OK':>7}")
    print(f"  {'-'*45} {'-'*5} {'-'*8} {'-'*10} {'-'*7}")

    demo_results = []
    for r in rows:
        d_lon, d_lat = r["d_lon"], r["d_lat"]
        s_lon, s_lat = r["s_lon"], r["s_lat"]
        dist = osrm_walking_distance(d_lon, d_lat, s_lon, s_lat)
        stype = r.get("school_type", "ZS")
        # §44 threshold: ZŠ ≤ 2 km walking for lower grades
        threshold = 2000
        within = (dist is not None and dist <= threshold)
        name = r["district_name"][:45]
        dist_str = f"{dist:.0f}" if dist is not None else "OSRM_FAIL"
        print(f"  {name:<45} {stype:<5} {dist_str:>8} {threshold:>10} {'YES' if within else 'NO':>7}")
        demo_results.append({"name": name, "dist_m": dist, "within": within})

    SUMMARY["demo_districts"] = len(rows)
    SUMMARY["demo_within_threshold"] = sum(1 for d in demo_results if d["within"])


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def print_final_summary() -> None:
    _section("FINAL SUMMARY")
    for k, v in SUMMARY.items():
        print(f"  {k}: {v}")

    if BLOCKER_LOG:
        print("\nBLOCKERS:")
        for b in BLOCKER_LOG:
            print(f"  [{b['source']}] {b['reason']}")
    else:
        print("\nNo blockers.")


def main() -> int:
    validate_config()
    print("Sprint 2 ingest starting...")
    print(f"Target: {SUPABASE_URL[:50]}")

    # TASK 1
    task1_filter_schools()

    # TASK 2
    task2_create_tables()
    muni_map = _get_muni_map()
    load_mrk_atlas(muni_map)
    load_mrk_buildings()
    load_transit_stops()
    load_road_network()
    load_demographics_children(muni_map)

    # TASK 3
    task3_derive_district_geometry()
    link_district_schools()

    # Topology + demo
    topology_checks()
    walking_distance_demo()

    print_final_summary()
    return 1 if BLOCKER_LOG else 0


if __name__ == "__main__":
    sys.exit(main())
