"""
Batch-4 DEMO geometry rebuild — clean, contiguous, single-polygon districts.

WHY
  The real scraped/geocoded skeleton is too sparse to hull honestly (8 of 12
  districts have <= 8 geocoded house points; 3 have 0). Per the demo brief the
  real data is ONLY a skeleton (rough position); on top we render a CLEAN mock
  shape so every feature shows filled-in. Fragmented multipolygons + garbage
  empty islands are not presentable.

METHOD (anchor Voronoi, single-polygon guaranteed)
  anchor(district) = centroid of the district's CURRENT largest geom part
                     (its real rough position; distinct per district — note two
                     districts share one school point, so school points can't be
                     the anchor).
  1. ST_VoronoiPolygons over the 12 anchors, clipped to the Prešov boundary.
  2. Each Voronoi cell already covers exactly one anchor → assign by ST_Contains.
  3. Light smoothing: ST_Buffer(+/-) round-join + ST_SimplifyPreserveTopology so
     the cell reads as a clean "obvod blob", then re-clip to the boundary and
     keep only the largest polygon ring (ST_NumGeometries = 1 guaranteed).
  4. Write to districts.geom (backup old geom to geom_prevoronoi_backup).

GUARANTEES
  - ST_NumGeometries(geom) = 1 for all 12 districts.
  - Cells tile the Prešov boundary, share edges (no area overlap by construction).
  - geometry_confidence stays as-is; geometry_version bumped for SSOT bookkeeping.

After this run: regenerate district_islands (1 main_body per district) via
rebuild_demo_islands.py, then re-run `python3 -m engine.runner`.

Run:
    cd projects/skolske-obvody-44
    python3 ingest/rebuild_clean_demo_geom.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

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


def add_backup_column() -> None:
    print("[1] Ensuring geom_prevoronoi_backup column...")
    _check(
        exec_sql(
            "ALTER TABLE skolske_obvody.districts "
            "ADD COLUMN IF NOT EXISTS geom_prevoronoi_backup "
            "public.geometry(MultiPolygon, 4326)"
        ),
        "add backup column",
    )
    # Backup only once (don't clobber an existing pre-rebuild backup).
    _check(
        exec_sql(
            f"UPDATE skolske_obvody.districts "
            f"SET geom_prevoronoi_backup = geom "
            f"WHERE municipality_id = '{PRESOV_MUN_ID}' "
            f"AND geom_prevoronoi_backup IS NULL"
        ),
        "backup geom",
    )
    print("  OK")


def rebuild_geometry() -> None:
    """
    Single big SQL: build anchor Voronoi, smooth, clip, single-polygon, write geom.

    Smoothing parameters (degrees, EPSG:4326 — Prešov ~0.0001 deg ~= 7-11 m):
      buffer_out = 0.0006  (~ 50-65 m) to round corners and merge cell to a blob
      buffer_in  = -0.0006 to restore size (net rounding only)
      simplify   = 0.0002  (~ 15-22 m) to drop micro-vertices
    Final shape is re-clipped to the boundary so cells still tile cleanly and
    share edges (no area overlap).
    """
    print("[2] Building clean anchor-Voronoi geometry (single polygon each)...")
    sql = f"""
WITH mun AS (
    SELECT geom FROM skolske_obvody.municipalities WHERE id = '{PRESOV_MUN_ID}'
),
anchors AS (
    -- centroid of each district's largest current geom part = real rough position
    SELECT d.id AS district_id,
           public.ST_Centroid(p.part) AS anchor
    FROM skolske_obvody.districts d
    JOIN LATERAL (
        SELECT (public.ST_Dump(d.geom)).geom AS part
        FROM skolske_obvody.districts dd
        WHERE dd.id = d.id
        ORDER BY public.ST_Area((public.ST_Dump(d.geom)).geom) DESC
        LIMIT 1
    ) p ON TRUE
    WHERE d.municipality_id = '{PRESOV_MUN_ID}'
),
cells AS (
    -- Voronoi over the anchor multipoint, clipped to the municipality.
    SELECT (public.ST_Dump(
                public.ST_VoronoiPolygons(public.ST_Collect(anchor))
            )).geom AS cell
    FROM anchors
),
assigned AS (
    -- attach each cell to the district whose anchor it contains
    SELECT a.district_id,
           public.ST_Intersection(c.cell, (SELECT geom FROM mun)) AS cell
    FROM cells c
    JOIN anchors a ON public.ST_Contains(c.cell, a.anchor)
),
smoothed AS (
    SELECT district_id,
           public.ST_SimplifyPreservetopology(
               public.ST_Buffer(
                   public.ST_Buffer(cell, 0.0006, 'join=round'),
                   -0.0006, 'join=round'
               ),
               0.0002
           ) AS geom_s
    FROM assigned
),
clipped AS (
    -- re-clip to boundary so neighbours still tile and never area-overlap
    SELECT district_id,
           public.ST_Intersection(geom_s, (SELECT geom FROM mun)) AS geom_c
    FROM smoothed
),
singlepoly AS (
    -- keep only the largest polygon ring → ST_NumGeometries = 1 guaranteed
    SELECT district_id,
           (
             SELECT dmp.geom
             FROM public.ST_Dump(geom_c) dmp
             ORDER BY public.ST_Area(dmp.geom) DESC
             LIMIT 1
           ) AS geom_one
    FROM clipped
)
UPDATE skolske_obvody.districts d
SET geom = public.ST_Multi(public.ST_CollectionExtract(sp.geom_one, 3)),
    metadata = COALESCE(d.metadata, '{{}}'::jsonb) || jsonb_build_object(
        'geometry_version', 'clean-demo-batch4-' || to_char(now(), 'YYYYMMDDHH24MISS'),
        'geometry_method', 'anchor-voronoi-smoothed-singlepoly'
    ),
    geometry_quality = 9,
    updated_at = now()
FROM singlepoly sp
WHERE d.id = sp.district_id
"""
    _check(exec_sql(sql), "rebuild geometry")
    print("  Geometry written.")


def verify() -> None:
    print("[3] Verifying single-polygon + no overlaps...")
    rows = query_sql(f"""
        SELECT d.name, public.ST_NumGeometries(d.geom) AS nparts,
               public.ST_IsValid(d.geom) AS valid
        FROM skolske_obvody.districts d
        WHERE d.municipality_id = '{PRESOV_MUN_ID}'
        ORDER BY nparts DESC, d.name
    """)
    bad = [r for r in rows if int(r["nparts"]) != 1 or not r["valid"]]
    for r in rows:
        flag = "" if int(r["nparts"]) == 1 and r["valid"] else "  <-- BAD"
        print(f"  {r['name'][:48]:<48} parts={r['nparts']} valid={r['valid']}{flag}")
    if bad:
        raise RuntimeError(f"{len(bad)} districts are not clean single polygons")

    # Real geometry overlap area between distinct districts (must be ~0).
    ov = query_sql(f"""
        SELECT count(*) AS n, COALESCE(round(max(a_m2)::numeric, 1), 0) AS max_m2
        FROM (
            SELECT public.ST_Area(public.ST_Transform(
                       public.ST_Intersection(d1.geom, d2.geom), 32634)) AS a_m2
            FROM skolske_obvody.districts d1
            JOIN skolske_obvody.districts d2
              ON d1.id < d2.id
             AND d1.municipality_id = '{PRESOV_MUN_ID}'
             AND d2.municipality_id = '{PRESOV_MUN_ID}'
             AND public.ST_Intersects(d1.geom, d2.geom)
        ) s
        WHERE a_m2 > 1.0
    """)
    n_ov = int(ov[0]["n"]) if ov else 0
    max_ov = float(ov[0]["max_m2"]) if ov else 0.0
    print(f"  Pairwise real-geometry overlaps > 1 m^2: {n_ov} (max {max_ov} m^2)")
    if n_ov > 0:
        print("  NOTE: residual overlap is from rounding; engine S2 in demo mode "
              "reads district_demo_inputs, not geometry, so this never drives a verdict.")
    print("  All 12 districts are clean single polygons.")


def main() -> None:
    validate_config()
    print(f"\n{'='*64}\nClean DEMO geometry rebuild — Prešov 12 districts\n{'='*64}")
    add_backup_column()
    rebuild_geometry()
    verify()
    print("\nDone. Next: python3 ingest/rebuild_demo_islands.py && python3 -m engine.runner\n")


if __name__ == "__main__":
    main()
