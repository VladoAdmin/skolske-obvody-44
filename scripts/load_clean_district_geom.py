"""
Sprint M-2 — Load data/clean_district_geom.geojson into districts.geom_clean.

UPSERT strategy: match by district id (uuid stored in feature.id), write
GeoJSON via ST_GeomFromGeoJSON. Sets geom_clean_metadata to the feature's
properties.method + demo flag so the public view can expose it.

Usage:
  python3 scripts/load_clean_district_geom.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.supabase_client import exec_sql, query_sql  # noqa: E402

GEOJSON_PATH = ROOT / "data" / "clean_district_geom.geojson"


def main() -> int:
    if not GEOJSON_PATH.exists():
        print(
            f"[load_clean_district_geom] FATAL: {GEOJSON_PATH} not found — "
            f"run scripts/build_clean_district_geom.py first"
        )
        return 1

    fc = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    features = fc.get("features", [])
    if not features:
        print("[load_clean_district_geom] no features in geojson — aborting")
        return 1

    print(f"[load_clean_district_geom] applying {len(features)} features")
    updated = 0
    errors = []

    for feature in features:
        district_id = feature.get("id") or feature.get("properties", {}).get("id")
        if not district_id:
            errors.append(("?", "missing id"))
            continue

        geom_geojson = json.dumps(feature["geometry"], ensure_ascii=False)
        metadata_json = json.dumps(feature.get("properties", {}), ensure_ascii=False)

        # Dollar-quoted literals so embedded special chars are safe.
        sql = f"""
        UPDATE skolske_obvody.districts
        SET geom_clean = public.ST_Multi(
              public.ST_SetSRID(
                public.ST_GeomFromGeoJSON($_geom${geom_geojson}$_geom$),
                4326
              )
            ),
            geom_clean_metadata = $_meta${metadata_json}$_meta$::jsonb
        WHERE id = '{district_id}'::uuid
        """
        result = exec_sql(sql)
        if result.get("ok"):
            updated += 1
        else:
            errors.append((district_id, result.get("message", "")[:200]))

    print(f"[load_clean_district_geom] updated {updated}/{len(features)} rows")
    if errors:
        print(f"[load_clean_district_geom] {len(errors)} errors:")
        for did, msg in errors[:10]:
            print(f"  - {did}: {msg}")
        return 1

    # Sanity check: count rows visible via the public view.
    rows = query_sql("SELECT count(*) AS n FROM public.so_district_clean_geom")
    print(f"[load_clean_district_geom] public.so_district_clean_geom now has {rows[0]['n']} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
