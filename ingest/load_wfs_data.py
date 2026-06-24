"""
Sprint 1: Load REAL data from Geoportál PSK WFS into Supabase.

Tables populated (so_ prefix in public schema):
  so_regions         <- admunit_counties (PSK)
  so_municipalities  <- admunit_municipalities (665 obcí PSK)
  so_schools         <- mapa_regionalneho_skolstva (ZŠ + MŠ filter)
  so_mrk_atlas       <- wm_ark_municipal (Atlas MRK 2019)
  so_mrk_buildings   <- rsm_*_budovy (6 MRK obcí)
  so_transit_stops   <- autobusove_zastavky_pad + psk_zel_zastavky
  so_rail_lines      <- zeleznice
  so_road_network    <- cesty_1/2/3_triedy_ln
  so_demographics    <- so_age_structure_0_14_municipalities
  so_datasets        <- provenance catalogue

Run:
    export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
    python3 -m ingest.load_wfs_data
"""

import json
import sys
import traceback
from datetime import date, datetime

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
from ingest.supabase_client import upsert, count
from ingest.wfs_connector import fetch_wfs_layer, geojson_to_wkt, WFSError


BLOCKER_LOG: list[dict] = []
LOAD_SUMMARY: dict = {}


def _log_blocker(source: str, reason: str, url: str = "") -> None:
    entry = {
        "source": source,
        "reason": reason,
        "url": url,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    BLOCKER_LOG.append(entry)
    print(f"  BLOCKER [{source}]: {reason}", file=sys.stderr)


def load_datasets_catalogue() -> None:
    """Insert/upsert all dataset records into so_datasets."""
    print("\n=== Loading datasets catalogue ===")
    records = [get_dataset_record(k) for k in DATASETS]
    result = upsert("datasets", records, on_conflict="key")
    LOAD_SUMMARY["so_datasets"] = {
        "inserted": result["inserted"],
        "errors": len(result["errors"]),
    }
    if result["errors"]:
        for err in result["errors"]:
            print(f"  ERROR: {err}", file=sys.stderr)
    else:
        print(f"  OK: {result['inserted']} dataset records")


def load_regions() -> dict[str, str]:
    """
    Load PSK region boundary.
    Returns: {nuts_code: uuid} map for municipality FK linkage.
    Actually admunit_counties has no nuts — we use code='PSK'.
    """
    print("\n=== Loading regions (PSK) ===")
    try:
        features = fetch_wfs_layer(WFS_LAYER_REGIONS)
    except WFSError as e:
        _log_blocker("wfs_regions_psk", str(e), WFS_LAYER_REGIONS)
        return {}

    records = []
    for f in features:
        props = f["properties"]
        wkt = geojson_to_wkt(f)
        record = {
            "code": "PSK",  # forced — only PSK region in this WFS
            "name": props.get("nm4", "Prešovský samosprávny kraj"),
            "source_name": DATASETS["wfs_regions_psk"].name,
            "source_date": WFS_SOURCE_DATE,
        }
        if wkt:
            record["geom"] = f"SRID=4326;{wkt}"
        records.append(record)

    if records:
        result = upsert("regions", records, on_conflict="code")
        LOAD_SUMMARY["so_regions"] = {"inserted": result["inserted"]}
        print(f"  OK: {result['inserted']} regions")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  ERROR: {e}", file=sys.stderr)

    return {"PSK": "PSK"}  # simplified — actual UUID resolved by DB


def load_municipalities() -> dict[str, str]:
    """
    Load 665 PSK municipalities.
    Returns: {nuts_code: idn4} map for school FK linkage.
    """
    print("\n=== Loading municipalities (PSK, 665 expected) ===")
    try:
        features = fetch_wfs_layer(WFS_LAYER_MUNICIPALITIES, max_features=1000)
    except WFSError as e:
        _log_blocker("wfs_municipalities_psk", str(e), WFS_LAYER_MUNICIPALITIES)
        return {}

    records = []
    nuts_to_idn4: dict[str, int] = {}

    for f in features:
        props = f["properties"]
        idn4 = props.get("idn4")
        nuts = props.get("nuts", "")
        name = props.get("nm4", "")
        wkt = geojson_to_wkt(f)

        nuts_to_idn4[nuts] = idn4

        record = {
            # Use idn4 as integer code; schema uses TEXT code
            "code": str(idn4),
            "name": name,
            "nuts_code": nuts,
            "source_name": DATASETS["wfs_municipalities_psk"].name,
            "source_date": WFS_SOURCE_DATE,
        }
        if wkt:
            record["geom"] = f"SRID=4326;{wkt}"
        records.append(record)

    if records:
        result = upsert("municipalities", records, on_conflict="code")
        LOAD_SUMMARY["so_municipalities"] = {"inserted": result["inserted"]}
        print(f"  OK: {result['inserted']} municipalities")
        if result["errors"]:
            for e in result["errors"][:3]:
                print(f"  ERROR: {e}", file=sys.stderr)

    return {str(idn4): str(idn4) for _, idn4 in nuts_to_idn4.items()}


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
    """Public = zriadený obcou/mestom/VÚC; church and private = not public."""
    if not typ_zriad:
        return True
    t = typ_zriad.lower()
    return "súkromn" not in t and "cirkev" not in t


def _founder_type(typ_zriad: str) -> str:
    if not typ_zriad:
        return "municipality"
    t = typ_zriad.lower()
    for key, val in FOUNDER_TYPE_MAP.items():
        if key in t:
            return val
    return "municipality"


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

    for f in features:
        props = f["properties"]
        druh = props.get("nazov_druhu_skoly", "")
        school_type = _school_type(druh)

        # Only load ZŠ, MŠ, ZUŠ — skip jedálne, školský klub, etc.
        if school_type == "OTHER":
            skipped += 1
            continue

        wkt = geojson_to_wkt(f)
        kod_obce = str(props.get("kod_obce", ""))

        record = {
            "eduid": str(props.get("eduid", "")),
            "name": props.get("nazov_skoly", ""),
            "type": school_type,
            "is_public": _is_public_school(props.get("typ_zriadovatela", "")),
            "teaching_language": (props.get("vyuc_jazyk") or "SK").upper()[:5],
            "student_count": props.get("pocet_ziakov"),
            # capacity is NULL (EDUZBER GAP)
            "capacity": None,
            "municipality_code": kod_obce,
            "source_name": DATASETS["wfs_schools_psk"].name,
            "source_date": WFS_SOURCE_DATE,
            # Extra metadata stored as JSONB
            "raw_properties": json.dumps({
                "kodsko": props.get("kodsko"),
                "kodskoh": props.get("kodskoh"),
                "kod_okresu": props.get("kod_okresu"),
                "nazov_okresu": props.get("nazov_okresu"),
                "nazov_obce": props.get("nazov_obce"),
                "ulica_a_cislo": props.get("ulica_a_cislo"),
                "psc": props.get("psc"),
                "typ_zriadovatela": props.get("typ_zriadovatela"),
                "zam_spolu": props.get("zam_spolu"),
                "druh": druh,
            }, ensure_ascii=False),
        }
        if wkt:
            record["geom"] = f"SRID=4326;{wkt}"

        records.append(record)

    print(f"  Skipped {skipped} non-ZS/MS records (jedálne, školský klub, etc.)")

    if records:
        result = upsert("schools", records, on_conflict="eduid")
        LOAD_SUMMARY["so_schools"] = {"inserted": result["inserted"], "skipped": skipped}
        print(f"  OK: {result['inserted']} schools")
        if result["errors"]:
            for e in result["errors"][:3]:
                print(f"  ERROR: {e}", file=sys.stderr)


def load_mrk_atlas() -> None:
    """Load Atlas rómskych komunít 2019 polygons."""
    print("\n=== Loading Atlas MRK 2019 ===")
    try:
        features = fetch_wfs_layer(WFS_LAYER_MRK_ATLAS, max_features=500)
    except WFSError as e:
        _log_blocker("wfs_mrk_atlas_2019", str(e), WFS_LAYER_MRK_ATLAS)
        return

    records = []
    for f in features:
        props = f["properties"]
        wkt = geojson_to_wkt(f)
        record = {
            "nuts_code": str(props.get("nuts", props.get("IDN4", ""))),
            "municipality_name": props.get("NM4", ""),
            "district_name": props.get("NM3", ""),
            "idn4": props.get("IDN4"),
            "idn3": props.get("IDN3"),
            "population_2019": props.get("poc_2019"),
            "roma_share_2019": props.get("pod_2019"),
            "roma_count_2019": props.get("pocR_2019"),
            "population_2013": props.get("poc_2013"),
            "roma_share_2013": props.get("pod_2013"),
            "roma_count_2013": props.get("pocR_2013"),
            "source_name": DATASETS["wfs_mrk_atlas_2019"].name,
            "source_date": "2019-01-01",
            "geometry_quality": QUALITY_MRK_ATLAS,
        }
        if wkt:
            record["geom"] = f"SRID=4326;{wkt}"
        records.append(record)

    if records:
        result = upsert("mrk_atlas", records, on_conflict="nuts_code")
        LOAD_SUMMARY["so_mrk_atlas"] = {"inserted": result["inserted"]}
        print(f"  OK: {result['inserted']} MRK atlas polygons")
        if result["errors"]:
            for e in result["errors"][:3]:
                print(f"  ERROR: {e}", file=sys.stderr)


MRK_BUILDING_LAYERS = [
    (WFS_LAYER_MRK_VARHANOVCE, "Varhaňovce"),
    (WFS_LAYER_MRK_OSTROVANY, "Ostrovany"),
    (WFS_LAYER_MRK_KRIVANY, "Krivany"),
    (WFS_LAYER_MRK_DLHE_STRAZE, "Dlhé Stráže"),
    (WFS_LAYER_MRK_VARADKA, "Varadka"),
    (WFS_LAYER_MRK_CICAVA, "Čičava"),
]


def load_mrk_buildings() -> None:
    """Load MRK occupied buildings for 6 PSK municipalities."""
    print("\n=== Loading MRK buildings (6 obcí) ===")
    all_records = []

    for layer, obec_name in MRK_BUILDING_LAYERS:
        try:
            features = fetch_wfs_layer(layer, max_features=2000)
            for f in features:
                props = f["properties"]
                wkt = geojson_to_wkt(f)
                record = {
                    "municipality_name": obec_name,
                    "building_id": str(props.get("id", "")),
                    "building_name": props.get("nazov_budovy", ""),
                    "building_type": props.get("typ_budovy", ""),
                    "floor_count": props.get("pocet_podlazi"),
                    "condition": props.get("stav_budovy", ""),
                    "source_name": f"RSM Geoportál PSK — {obec_name}",
                    "source_date": WFS_SOURCE_DATE,
                    "geometry_quality": QUALITY_MRK_BUILDINGS,
                }
                if wkt:
                    record["geom"] = f"SRID=4326;{wkt}"
                all_records.append(record)
            print(f"  {obec_name}: {len(features)} buildings")
        except WFSError as e:
            _log_blocker(f"wfs_mrk_buildings_{obec_name}", str(e), layer)

    if all_records:
        result = upsert("mrk_buildings", all_records, on_conflict="building_id")
        LOAD_SUMMARY["so_mrk_buildings"] = {"inserted": result["inserted"]}
        print(f"  OK: {result['inserted']} MRK buildings total")
        if result["errors"]:
            for e in result["errors"][:3]:
                print(f"  ERROR: {e}", file=sys.stderr)


def load_transit_stops() -> None:
    """Load PAD bus stops and rail stops."""
    print("\n=== Loading transit stops (PAD + rail) ===")
    all_records = []

    # PAD bus stops
    try:
        features = fetch_wfs_layer(WFS_LAYER_PAD_BUS_STOPS, max_features=5000)
        for f in features:
            props = f["properties"]
            wkt = geojson_to_wkt(f)
            record = {
                "stop_id": str(props.get("id", "")),
                "name": props.get("Name", ""),
                "stop_type": "bus",
                "district_name": props.get("NM3", ""),
                "has_shelter": bool(props.get("shelter")),
                "source_name": DATASETS["wfs_pad_bus_stops"].name,
                "source_date": WFS_SOURCE_DATE,
                "geometry_quality": QUALITY_PAD_STOPS,
            }
            if wkt:
                record["geom"] = f"SRID=4326;{wkt}"
            all_records.append(record)
        print(f"  PAD bus stops: {len(features)}")
    except WFSError as e:
        _log_blocker("wfs_pad_bus_stops", str(e), WFS_LAYER_PAD_BUS_STOPS)

    # Rail stops
    try:
        features = fetch_wfs_layer(WFS_LAYER_RAIL_STOPS, max_features=500)
        for f in features:
            props = f["properties"]
            wkt = geojson_to_wkt(f)
            record = {
                "stop_id": f"rail_{props.get('id', props.get('stop_id', ''))}",
                "name": props.get("stop_name", ""),
                "stop_type": "rail",
                "district_name": props.get("NM3", ""),
                "has_shelter": bool(props.get("cakaren")),
                "source_name": DATASETS["wfs_rail_stops"].name,
                "source_date": WFS_SOURCE_DATE,
                "geometry_quality": QUALITY_RAIL,
            }
            if wkt:
                record["geom"] = f"SRID=4326;{wkt}"
            all_records.append(record)
        print(f"  Rail stops: {len(features)}")
    except WFSError as e:
        _log_blocker("wfs_rail_stops", str(e), WFS_LAYER_RAIL_STOPS)

    if all_records:
        result = upsert("transit_stops", all_records, on_conflict="stop_id")
        LOAD_SUMMARY["so_transit_stops"] = {"inserted": result["inserted"]}
        print(f"  OK: {result['inserted']} transit stops total")
        if result["errors"]:
            for e in result["errors"][:3]:
                print(f"  ERROR: {e}", file=sys.stderr)


def load_road_network() -> None:
    """Load road network categories I/II/III."""
    print("\n=== Loading road network (I/II/III) ===")
    all_records = []

    road_layers = [
        (WFS_LAYER_ROADS_I, "I", DATASETS["wfs_roads_i"].name),
        (WFS_LAYER_ROADS_II, "II", DATASETS["wfs_roads_ii"].name),
        (WFS_LAYER_ROADS_III, "III", DATASETS["wfs_roads_iii"].name),
    ]

    for layer, category, source_name in road_layers:
        try:
            features = fetch_wfs_layer(layer, max_features=WFS_MAX_FEATURES)
            for f in features:
                props = f["properties"]
                wkt = geojson_to_wkt(f)
                record = {
                    "road_id": str(props.get("id", props.get("cislopk", f"{category}_{len(all_records)}"))),
                    "category": category,
                    "road_number": str(props.get("cislopk", "")),
                    "manager": props.get("spravca", ""),
                    "length_m": props.get("dlzka"),
                    "source_name": source_name,
                    "source_date": WFS_SOURCE_DATE,
                    "geometry_quality": QUALITY_ROADS,
                }
                if wkt:
                    record["geom"] = f"SRID=4326;{wkt}"
                all_records.append(record)
            print(f"  Roads category {category}: {len(features)}")
        except WFSError as e:
            _log_blocker(f"wfs_roads_{category.lower()}", str(e), layer)

    if all_records:
        result = upsert("road_network", all_records, on_conflict="road_id")
        LOAD_SUMMARY["so_road_network"] = {"inserted": result["inserted"]}
        print(f"  OK: {result['inserted']} road segments total")
        if result["errors"]:
            for e in result["errors"][:3]:
                print(f"  ERROR: {e}", file=sys.stderr)


def load_demographics() -> None:
    """Load children 0-14 per municipality (proxy for school demand)."""
    print("\n=== Loading demographics (children 0–14) ===")
    try:
        features = fetch_wfs_layer(WFS_LAYER_CHILDREN_0_14, max_features=1000)
    except WFSError as e:
        _log_blocker("wfs_children_0_14", str(e), WFS_LAYER_CHILDREN_0_14)
        return

    records = []
    for f in features:
        props = f["properties"]
        record = {
            "nuts_code": props.get("nuts", ""),
            "municipality_name": props.get("nm4", ""),
            "children_0_14_last": props.get("_last"),
            "children_0_14_2020": props.get("_2020"),
            "children_0_14_2019": props.get("_2019"),
            "total_population": props.get("pocet_obyvatelov_spolu"),
            "share_pct_last": props.get("podiel_na_celkovom_pocte_ob_perc_last"),
            "source_name": DATASETS["wfs_children_0_14"].name,
            "source_date": WFS_SOURCE_DATE,
        }
        records.append(record)

    if records:
        result = upsert("demographics_children", records, on_conflict="nuts_code")
        LOAD_SUMMARY["so_demographics"] = {"inserted": result["inserted"]}
        print(f"  OK: {result['inserted']} municipality demographics")
        if result["errors"]:
            for e in result["errors"][:3]:
                print(f"  ERROR: {e}", file=sys.stderr)


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


def main() -> int:
    validate_config()

    print("Starting Sprint 1 WFS data load...")
    print(f"Target: {__import__('ingest.config', fromlist=['SUPABASE_URL']).SUPABASE_URL}")

    load_datasets_catalogue()
    muni_map = load_municipalities()
    load_regions()
    load_schools(muni_map)
    load_mrk_atlas()
    load_mrk_buildings()
    load_transit_stops()
    load_road_network()
    load_demographics()

    print_summary()

    return 1 if BLOCKER_LOG else 0


if __name__ == "__main__":
    sys.exit(main())
