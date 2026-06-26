"""
Sprint 1: Load REAL data from Geoportál PSK WFS into Supabase.

Schema: skolske_obvody (all writes via f2_exec_sql bridge)

Tables populated:
  skolske_obvody.datasets        <- provenance catalogue
  skolske_obvody.regions         <- admunit_counties (PSK)
  skolske_obvody.municipalities  <- admunit_municipalities (665 obcí PSK)
  skolske_obvody.schools         <- mapa_regionalneho_skolstva (ZŠ + MŠ)

Tables NOT in schema (v1 schema — deferred):
  mrk_atlas, mrk_buildings, transit_stops, road_network,
  demographics_children — logged as DEFERRED (not a blocker).

Run:
    export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
    python3 -m ingest.load_wfs_data
"""

import json
import sys
import traceback
from datetime import date, datetime
from typing import Optional

from ingest.config import (
    validate_config,
    WFS_SOURCE_DATE,
    WFS_LAYER_SCHOOLS,
    WFS_LAYER_MUNICIPALITIES,
    WFS_LAYER_REGIONS,
    WFS_LAYER_MRK_ATLAS,
    WFS_LAYER_MRK_VARHANOVCE,
    WFS_LAYER_MRK_OSTROVANY,
    WFS_LAYER_MRK_KRIVANY,
    WFS_LAYER_MRK_DLHE_STRAZE,
    WFS_LAYER_MRK_VARADKA,
    WFS_LAYER_MRK_CICAVA,
    WFS_LAYER_PAD_BUS_STOPS,
    WFS_LAYER_RAIL_LINES,
    WFS_LAYER_RAIL_STOPS,
    WFS_LAYER_ROADS_I,
    WFS_LAYER_ROADS_II,
    WFS_LAYER_ROADS_III,
    WFS_LAYER_CHILDREN_0_14,
    QUALITY_SCHOOLS_WFS,
    QUALITY_MUNICIPALITIES,
    QUALITY_REGIONS,
    QUALITY_MRK_ATLAS,
    QUALITY_MRK_BUILDINGS,
    QUALITY_PAD_STOPS,
    QUALITY_RAIL,
    QUALITY_ROADS,
    QUALITY_CHILDREN_0_14,
)
from ingest.data_key import DATASETS, get_dataset_record
from ingest.supabase_client import upsert, count, query_sql
from ingest.wfs_connector import fetch_wfs_layer, geojson_to_wkt, WFSError


BLOCKER_LOG: list[dict] = []
LOAD_SUMMARY: dict = {}


def _to_multipolygon_ewkt(wkt: str) -> str:
    """
    Ensure WKT is wrapped as MULTIPOLYGON for the schema column type.
    Shapely returns POLYGON for single-ring geometries; PostGIS requires
    MULTIPOLYGON for GEOMETRY(MultiPolygon, 4326) columns.
    """
    upper = wkt.upper().strip()
    if upper.startswith("MULTIPOLYGON"):
        return f"SRID=4326;{wkt}"
    if upper.startswith("POLYGON"):
        # Wrap: POLYGON ((...)) → MULTIPOLYGON (((...)))
        inner = wkt[wkt.index("("):]   # "((..., ...))"
        return f"SRID=4326;MULTIPOLYGON({inner})"
    # LineString / Point — return as-is with SRID
    return f"SRID=4326;{wkt}"


def _log_blocker(source: str, reason: str, url: str = "") -> None:
    entry = {
        "source": source,
        "reason": reason,
        "url": url,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    BLOCKER_LOG.append(entry)
    print(f"  BLOCKER [{source}]: {reason}", file=sys.stderr)


def _log_deferred(source: str, reason: str) -> None:
    print(f"  DEFERRED [{source}]: {reason}")


def load_datasets_catalogue() -> None:
    """Insert/upsert all dataset records into datasets."""
    print("\n=== Loading datasets catalogue ===")
    records = []
    for k in DATASETS:
        rec = get_dataset_record(k)
        # datasets schema: key, name, source_url, description, completeness, validity, version, fetched_at, status
        # source_date in get_dataset_record is not a column — drop it
        records.append({
            "key": rec["key"],
            "name": rec["name"],
            "source_url": rec["source_url"],
            "description": rec["description"],
            "completeness": rec["completeness"],
            "validity": rec["validity"],
            "version": rec["version"],
            "fetched_at": rec["fetched_at"],
            "status": rec["status"],
        })

    result = upsert("datasets", records, on_conflict="key")
    LOAD_SUMMARY["datasets"] = {
        "inserted": result["inserted"],
        "errors": len(result["errors"]),
    }
    if result["errors"]:
        for err in result["errors"]:
            print(f"  ERROR: {err}", file=sys.stderr)
    else:
        print(f"  OK: {result['inserted']} dataset records")


def load_regions() -> Optional[str]:
    """
    Load PSK region boundary.
    Returns region UUID string for municipality FK linkage, or None on failure.
    """
    print("\n=== Loading regions (PSK) ===")
    try:
        features = fetch_wfs_layer(WFS_LAYER_REGIONS)
    except WFSError as e:
        _log_blocker("wfs_regions_psk", str(e), WFS_LAYER_REGIONS)
        return None

    records = []
    for f in features:
        props = f["properties"]
        wkt = geojson_to_wkt(f)
        record = {
            "code": "PSK",
            "name": props.get("nm4", "Prešovský samosprávny kraj"),
        }
        if wkt:
            record["geom"] = _to_multipolygon_ewkt(wkt)
        records.append(record)

    if not records:
        _log_blocker("wfs_regions_psk", "No features returned from WFS")
        return None

    result = upsert("regions", records, on_conflict="code")
    LOAD_SUMMARY["regions"] = {"inserted": result["inserted"]}
    print(f"  OK: {result['inserted']} regions")
    if result["errors"]:
        for e in result["errors"]:
            print(f"  ERROR: {e}", file=sys.stderr)

    # Retrieve the UUID of the PSK region
    rows = query_sql(
        "SELECT id FROM skolske_obvody.regions WHERE code = 'PSK' LIMIT 1"
    )
    if rows:
        region_uuid = rows[0]["id"]
        print(f"  PSK region UUID: {region_uuid}")
        return region_uuid

    _log_blocker("wfs_regions_psk", "Inserted but could not retrieve PSK region UUID")
    return None


def load_municipalities(region_uuid: str) -> dict[str, str]:
    """
    Load 665 PSK municipalities.
    Returns: {code: uuid} map for school FK linkage.
    """
    print("\n=== Loading municipalities (PSK, 665 expected) ===")
    try:
        features = fetch_wfs_layer(WFS_LAYER_MUNICIPALITIES, max_features=1000)
    except WFSError as e:
        _log_blocker("wfs_municipalities_psk", str(e), WFS_LAYER_MUNICIPALITIES)
        return {}

    records = []
    for f in features:
        props = f["properties"]
        idn4 = props.get("idn4")
        nuts = props.get("nuts", "")
        name = props.get("nm4", "")
        wkt = geojson_to_wkt(f)

        record = {
            "region_id": region_uuid,
            "code": str(idn4),
            "name": name,
            "minority_language": None,
        }
        if wkt:
            record["geom"] = _to_multipolygon_ewkt(wkt)
        records.append(record)

    if not records:
        _log_blocker("wfs_municipalities_psk", "No features returned from WFS")
        return {}

    result = upsert("municipalities", records, on_conflict="code")
    LOAD_SUMMARY["municipalities"] = {"inserted": result["inserted"]}
    print(f"  OK: {result['inserted']} municipalities")
    if result["errors"]:
        for e in result["errors"][:3]:
            print(f"  ERROR: {e}", file=sys.stderr)

    # Build code→uuid map by querying back
    print("  Building municipality code→UUID map...")
    rows = query_sql(
        "SELECT id, code FROM skolske_obvody.municipalities LIMIT 2000"
    )
    code_to_uuid: dict[str, str] = {row["code"]: row["id"] for row in rows}
    print(f"  Built map with {len(code_to_uuid)} entries")
    return code_to_uuid


# School type mapping from nazov_druhu_skoly
SCHOOL_TYPE_MAP = {
    "základná škola": "ZS",
    "materská škola": "MS",
    "základná umelecká škola": "ZUS",
    "špeciálna základná škola": "ZS_SPECIAL",
    "cirkevná základná škola": "ZS",
    "súkromná základná škola": "ZS",
    "cirkevná materská škola": "MS",
    "súkromná materská škola": "MS",
}

FOUNDER_TYPE_MAP = {
    "obec": "municipality",
    "mesto": "municipality",
    "mestská časť": "municipality",
    "samosprávny kraj": "state",
    "cirkev": "church",
    "súkromná osoba": "private",
    "iný zriaďovateľ": "private",
}


def _school_type(druh: str) -> str:
    druh_lower = druh.lower() if druh else ""
    for key, val in SCHOOL_TYPE_MAP.items():
        if key in druh_lower:
            return val
    return "OTHER"


def _is_public_school(typ_zriad: str) -> bool:
    if not typ_zriad:
        return True
    t = typ_zriad.lower()
    return "súkromn" not in t and "cirkev" not in t


def load_schools(municipality_map: dict[str, str]) -> None:
    """Load schools from WFS. Only ZŠ and MŠ (filter out školské jedálne etc.)."""
    print("\n=== Loading schools (ZŠ + MŠ filter) ===")
    try:
        features = fetch_wfs_layer(WFS_LAYER_SCHOOLS, max_features=5000)
    except WFSError as e:
        _log_blocker("wfs_schools_psk", str(e), WFS_LAYER_SCHOOLS)
        return

    records = []
    skipped = 0
    no_municipality = 0

    for f in features:
        props = f["properties"]
        druh = props.get("nazov_druhu_skoly", "")
        school_type = _school_type(druh)

        # Only load ZŠ, MŠ, ZUŠ — skip jedálne, školský klub, etc.
        if school_type == "OTHER":
            skipped += 1
            continue

        kod_obce = str(props.get("kod_obce", ""))
        municipality_uuid = municipality_map.get(kod_obce)
        if not municipality_uuid:
            no_municipality += 1
            continue  # Skip schools without resolved municipality FK

        wkt = geojson_to_wkt(f)

        record = {
            "municipality_id": municipality_uuid,
            "eduid": str(props.get("eduid", "")),
            "name": props.get("nazov_skoly", ""),
            "type": school_type,
            "is_public": _is_public_school(props.get("typ_zriadovatela", "")),
            "teaching_language": (props.get("vyuc_jazyk") or "SK").upper()[:5],
            "student_count": props.get("pocet_ziakov"),
            "capacity": None,
            "source_name": DATASETS["wfs_schools_psk"].name,
            "source_date": WFS_SOURCE_DATE,
        }
        if wkt:
            record["geom"] = f"SRID=4326;{wkt}"

        records.append(record)

    print(f"  Skipped {skipped} non-ZS/MS records (jedálne, školský klub, etc.)")
    if no_municipality:
        print(f"  Skipped {no_municipality} schools with unresolved municipality FK")

    if records:
        result = upsert("schools", records, on_conflict="eduid")
        LOAD_SUMMARY["schools"] = {"inserted": result["inserted"], "skipped": skipped}
        print(f"  OK: {result['inserted']} schools")
        if result["errors"]:
            for e in result["errors"][:3]:
                print(f"  ERROR: {e}", file=sys.stderr)


def load_deferred_tables() -> None:
    """
    Log tables that exist in the WFS source but have no corresponding table
    in the current skolske_obvody schema (v1). These are deferred to Sprint 2.
    """
    deferred = [
        ("mrk_atlas", "Table skolske_obvody.mrk_atlas not in schema v1; deferred to Sprint 2"),
        ("mrk_buildings", "Table skolske_obvody.mrk_buildings not in schema v1; deferred to Sprint 2"),
        ("transit_stops", "Table skolske_obvody.transit_stops not in schema v1; deferred to Sprint 2"),
        ("road_network", "Table skolske_obvody.road_network not in schema v1; deferred to Sprint 2"),
        ("demographics_children", "Table skolske_obvody.demographics_children not in schema v1; deferred to Sprint 2"),
    ]
    print("\n=== Deferred tables (not in schema v1) ===")
    for table, reason in deferred:
        _log_deferred(table, reason)
        LOAD_SUMMARY[table] = {"inserted": 0, "note": "deferred_sprint2"}


def print_summary() -> None:
    print("\n" + "=" * 60)
    print("LOAD SUMMARY")
    print("=" * 60)
    for table, stats in LOAD_SUMMARY.items():
        print(f"  {table}: {stats}")

    if BLOCKER_LOG:
        print("\nBLOCKERS (sources that were unreachable or failed):")
        for b in BLOCKER_LOG:
            print(f"  [{b['source']}] {b['reason']}")
    else:
        print("\nNo blockers.")

    print("=" * 60)


def print_row_counts() -> None:
    """Query live counts for all core tables and print them."""
    print("\n=== Live row counts (f2_query_sql) ===")
    tables = ["datasets", "regions", "municipalities", "schools", "vzns", "districts"]
    for t in tables:
        try:
            c = count(t)
            print(f"  skolske_obvody.{t}: {c} rows")
        except Exception as e:
            print(f"  skolske_obvody.{t}: ERROR — {e}")


def main() -> int:
    validate_config()

    print("Starting Sprint 1 WFS data load...")
    import ingest.config as _cfg
    print(f"Target: {_cfg.SUPABASE_URL}")

    load_datasets_catalogue()
    region_uuid = load_regions()
    if not region_uuid:
        print("FATAL: Could not load PSK region. Aborting.", file=sys.stderr)
        print_summary()
        return 1

    muni_map = load_municipalities(region_uuid)
    load_schools(muni_map)
    load_deferred_tables()

    print_summary()
    print_row_counts()

    return 1 if BLOCKER_LOG else 0


if __name__ == "__main__":
    sys.exit(main())
