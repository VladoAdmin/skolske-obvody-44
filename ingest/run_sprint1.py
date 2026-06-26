"""
Sprint 1 master ingest runner.

Runs in order:
  1. load_wfs_data   — regions, municipalities, schools
  2. vzn_ingest      — VZN Prešov 1/2023 → vzns + districts (no geom)

Geometry for districts is deferred (address_points not loaded — minv.sk 404).
Districts inserted with geom=NULL, geometry_confidence='pending'.

Run:
    python3 -m ingest.run_sprint1
"""

import sys

from ingest.config import validate_config
from ingest.supabase_client import upsert, query_sql, exec_sql
from ingest.vzn_parser import (
    load_and_parse_vzn,
    VZN_FULL_TEXT,
    VZN_SOURCE_DATE,
    VZN_SOURCE_URL,
    MUNICIPALITY_NAME,
    MUNICIPALITY_NUTS,
)
import json
import hashlib
from typing import Optional


def load_vzn(presov_muni_uuid: str) -> Optional[str]:
    """
    Insert VZN Prešov 1/2023 record.
    Returns the VZN UUID on success, None on failure.
    """
    print("\n=== Loading VZN Prešov 1/2023 ===")

    text_hash = hashlib.sha256(VZN_FULL_TEXT.encode("utf-8")).hexdigest()

    vzn_records = [{
        "municipality_id": presov_muni_uuid,
        "reference": "VZN 1/2023",
        "title": "VZN mesta Prešov č. 1/2023 o určení školských obvodov",
        "effective_date": VZN_SOURCE_DATE,
        "url": VZN_SOURCE_URL,
        "raw_text": VZN_FULL_TEXT,
        "hash": text_hash,
        "scrape_status": "ok",
        "parse_status": "parsed",
        "parsed_at": _now(),
        "parsed_by": "auto",
    }]

    result = upsert("vzns", vzn_records, on_conflict="municipality_id,reference")
    if result["errors"]:
        print(f"  ERROR inserting VZN: {result['errors']}", file=sys.stderr)
        return None

    # Retrieve UUID
    rows = query_sql(
        "SELECT id FROM skolske_obvody.vzns "
        "WHERE reference = 'VZN 1/2023' "
        "LIMIT 1"
    )
    if rows:
        vzn_uuid = rows[0]["id"]
        print(f"  OK: VZN inserted, UUID={vzn_uuid}")
        return vzn_uuid

    print("  ERROR: VZN inserted but UUID not retrieved", file=sys.stderr)
    return None


def load_districts(
    vzn_uuid: str,
    presov_muni_uuid: str,
) -> int:
    """
    Parse VZN and insert 12 district records (geom=NULL, pending geometry).
    Returns number of districts inserted.
    """
    print("\n=== Loading 12 school districts from VZN ===")
    districts_parsed = load_and_parse_vzn()
    print(f"  Parsed {len(districts_parsed)} districts from VZN text")

    records = []
    for d in districts_parsed:
        metadata = {
            "district_number": d.district_number,
            "school_address": d.school_address,
            "streets": d.streets,
            "street_qualifiers": d.street_qualifiers,
            "shared_municipalities": d.shared_municipalities,
            "streets_count": len(d.streets),
            "municipality_nuts": MUNICIPALITY_NUTS,
        }

        records.append({
            "municipality_id": presov_muni_uuid,
            "vzn_id": vzn_uuid,
            "vzn_article": f"Článok 3, obvod {d.district_number}",
            "name": d.school_name,
            "school_type": "ZS",
            "teaching_language": "SK",
            # geom intentionally omitted — NULL (address_points not loaded)
            "source_name": "VZN Prešov 1/2023",
            "source_date": VZN_SOURCE_DATE,
            "geometry_quality": 6,
            "geometry_confidence": "pending",
            "metadata": json.dumps(metadata, ensure_ascii=False),
        })

    if not records:
        print("  WARNING: No district records generated", file=sys.stderr)
        return 0

    # Districts have no natural unique key in this schema.
    # Use vzn_id + vzn_article as composite conflict target.
    # We need a unique constraint for this — use exec_sql to add if missing.
    _ensure_district_unique_constraint()

    result = upsert("districts", records, on_conflict="vzn_id,vzn_article")
    if result["errors"]:
        for e in result["errors"]:
            print(f"  ERROR: {e}", file=sys.stderr)

    print(f"  OK: {result['inserted']} districts (geom=pending)")
    return result["inserted"]


def _ensure_district_unique_constraint() -> None:
    """Add unique constraint on (vzn_id, vzn_article) if not present."""
    rows = query_sql(
        "SELECT 1 FROM pg_constraint c "
        "JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE n.nspname = 'skolske_obvody' "
        "AND c.conname = 'districts_vzn_article_unique'"
    )
    if rows:
        return  # already exists

    result = exec_sql(
        "ALTER TABLE skolske_obvody.districts "
        "ADD CONSTRAINT districts_vzn_article_unique "
        "UNIQUE (vzn_id, vzn_article)"
    )
    if not result.get("ok"):
        print(f"  WARNING: Could not add unique constraint: {result.get('message')}", file=sys.stderr)


def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


def find_presov_uuid() -> Optional[str]:
    """Look up Prešov's municipality UUID by name."""
    rows = query_sql(
        "SELECT id, name, code FROM skolske_obvody.municipalities "
        "WHERE name ILIKE '%Prešov%' OR name ILIKE '%Presov%' "
        "LIMIT 5"
    )
    print(f"  Municipalities matching 'Prešov': {rows}")
    if rows:
        return rows[0]["id"]
    return None


def main() -> int:
    validate_config()

    print("=" * 60)
    print("Sprint 1 Master Ingest")
    print("=" * 60)

    # Step 1: WFS data
    from ingest.load_wfs_data import main as wfs_main
    wfs_exit = wfs_main()

    # Step 2: VZN + districts
    presov_uuid = find_presov_uuid()
    if not presov_uuid:
        print("BLOCKER: Prešov not found in municipalities. VZN skipped.", file=sys.stderr)
        return 1

    vzn_uuid = load_vzn(presov_uuid)
    if not vzn_uuid:
        print("BLOCKER: VZN insert failed. Districts skipped.", file=sys.stderr)
        return 1

    n_districts = load_districts(vzn_uuid, presov_uuid)

    # Final counts
    print("\n=== Final row counts ===")
    tables = ["datasets", "regions", "municipalities", "schools", "vzns", "districts"]
    from ingest.supabase_client import count
    for t in tables:
        try:
            c = count(t)
            print(f"  skolske_obvody.{t}: {c}")
        except Exception as e:
            print(f"  skolske_obvody.{t}: ERROR {e}")

    return wfs_exit


if __name__ == "__main__":
    sys.exit(main())
