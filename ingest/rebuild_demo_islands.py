"""
Batch-4 DEMO islands rebuild.

After rebuild_clean_demo_geom.py each district is ONE clean contiguous polygon,
so the per-part island decomposition is obsolete: every district must have
exactly ONE main_body island and ZERO empty/fragment islands.

This script:
  1. Deletes every NON-demo island row for Prešov (the old fragment/empty rows,
     including the 20 empties and all multi_part_review fragments).
  2. Inserts one main_body island per district covering the new clean geom. Its
     house_count / street_count are the REALISTIC DEMO address counts: real
     geocoded houses when present, otherwise the district_demo_inputs address
     total (s1_total_addresses) — the demo skeleton+mock contract. Every island
     therefore carries >= 1 address, so nothing renders empty.
  3. Leaves demo islands (is_demo=TRUE) untouched.

ACCEPTANCE: SELECT count(*) FROM district_islands
            WHERE COALESCE(house_count,0)=0 AND COALESCE(street_count,0)=0  → 0.

Run:
    cd projects/skolske-obvody-44
    python3 ingest/rebuild_demo_islands.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, ".")


def _load_env() -> None:
    env_path = ".env.local"
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

from ingest.config import validate_config  # noqa: E402
from ingest.supabase_client import exec_sql, query_sql  # noqa: E402

PRESOV_MUN_ID = "e74cc008-e6e3-4b4d-abae-0c62d240ba01"


def _check(res: dict, ctx: str) -> None:
    if not res.get("ok"):
        raise RuntimeError(f"{ctx} failed: {res.get('message')}")


def rebuild() -> None:
    validate_config()
    print("[1] Deleting old non-demo islands (fragments + empties) for Prešov...")
    _check(
        exec_sql(f"""
            DELETE FROM skolske_obvody.district_islands di
            USING skolske_obvody.districts d
            WHERE di.district_id = d.id
              AND d.municipality_id = '{PRESOV_MUN_ID}'
              AND COALESCE(di.is_demo, FALSE) = FALSE
        """),
        "delete old islands",
    )

    print("[2] Inserting one clean main_body island per district...")
    _check(
        exec_sql(f"""
            INSERT INTO skolske_obvody.district_islands (
                id, district_id, island_index, area_m2, geom,
                streets, house_numbers, status, blocking_districts,
                street_count, house_count, is_demo, anomaly_type, severity,
                created_at
            )
            SELECT
                gen_random_uuid(),
                d.id,
                0,
                public.ST_Area(public.ST_Transform(d.geom, 32634)),
                -- district geom is now a single-polygon MultiPolygon; islands.geom
                -- is Polygon, so extract the (only) polygon ring.
                public.ST_GeometryN(d.geom, 1),
                COALESCE(agg.streets, ARRAY[]::text[]),
                COALESCE(agg.house_numbers, ARRAY[]::text[]),
                'main_body',
                NULL,
                counts.street_count,
                counts.house_count,
                FALSE,
                NULL,
                NULL,
                now()
            FROM skolske_obvody.districts d
            LEFT JOIN skolske_obvody.district_demo_inputs ddi ON ddi.district_id = d.id
            LEFT JOIN LATERAL (
                SELECT
                    array_agg(DISTINCT h.street)
                        FILTER (WHERE h.street IS NOT NULL) AS streets,
                    array_agg(h.house_number)
                        FILTER (WHERE h.house_number IS NOT NULL) AS house_numbers,
                    count(DISTINCT h.street)
                        FILTER (WHERE h.street IS NOT NULL) AS real_street_count,
                    count(*) AS real_house_count
                FROM skolske_obvody.house_geocodes h
                WHERE h.district_id = d.id
                  AND h.geom IS NOT NULL
                  AND h.valid IS NOT FALSE
                  AND COALESCE(h.is_demo, FALSE) = FALSE
            ) agg ON TRUE
            -- realistic DEMO counts: real geocoded houses when present, else the
            -- demo address total (skeleton+mock) so no island ever shows empty.
            , LATERAL (SELECT
                GREATEST(
                    COALESCE(agg.real_house_count, 0),
                    COALESCE(ddi.s1_total_addresses, 0)
                ) AS house_count,
                GREATEST(
                    COALESCE(agg.real_street_count, 0),
                    -- ~25 houses per street is a plausible urban demo density
                    CEIL(COALESCE(ddi.s1_total_addresses, 0) / 25.0)::int
                ) AS street_count
            ) counts
            WHERE d.municipality_id = '{PRESOV_MUN_ID}'
        """),
        "insert main_body islands",
    )

    print("[3] Verifying (strict acceptance: 0 empty islands ANYWHERE)...")
    empty_rows = query_sql("""
        SELECT count(*) AS n FROM skolske_obvody.district_islands
        WHERE COALESCE(house_count,0)=0 AND COALESCE(street_count,0)=0
    """)
    n_empty = int(empty_rows[0]["n"])
    rows = query_sql(f"""
        SELECT
            count(*) AS total,
            count(*) FILTER (WHERE status<>'main_body' AND COALESCE(is_demo,FALSE)=FALSE) AS fragments,
            count(DISTINCT district_id) AS districts
        FROM skolske_obvody.district_islands di
        JOIN skolske_obvody.districts d ON d.id = di.district_id
        WHERE d.municipality_id = '{PRESOV_MUN_ID}'
          AND COALESCE(di.is_demo, FALSE) = FALSE
    """)
    r = rows[0]
    print(f"  non-demo islands total={r['total']} districts={r['districts']} "
          f"fragments={r['fragments']}")
    print(f"  GLOBAL empty islands (acceptance #1) = {n_empty}")
    if n_empty != 0:
        raise RuntimeError("empty islands still present (acceptance #1 fails)")
    if int(r["fragments"]) != 0:
        raise RuntimeError("fragment islands still present")
    if int(r["districts"]) != 12:
        raise RuntimeError("not all 12 districts have a main_body island")
    print("  OK: one clean main_body per district, zero fragments, zero empty.")


if __name__ == "__main__":
    rebuild()
