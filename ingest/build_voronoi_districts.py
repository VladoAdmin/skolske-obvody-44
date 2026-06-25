"""
Sprint K — Build Voronoi-tessellated district polygons.

Uses PostGIS ST_VoronoiPolygons (GEOS-backed) for topologically correct results.

Math guarantee: Voronoi tessellation + PostGIS union gives exactly disjoint polygons.
ST_VoronoiPolygons generates cells sharing edges (not areas), so after unary_union
per district, ST_Intersection pair area = 0 exactly.

Pipeline:
  1. Collect all valid points (house_geocodes + street_geocodes range_type='all')
  2. PostGIS ST_VoronoiPolygons on full point cloud clipped to Prešov boundary
  3. Each cell: find owning district (the one whose input point is ST_Within the cell)
  4. ST_Union cells per district + ST_Intersection with boundary → MultiPolygon
  5. Write to districts.geom_voronoi + metadata
  6. Backup current geom → geom_sprint_j_backup
  7. Promote geom_voronoi → geom (confidence=high, quality=9)
  8. Island report (disconnected MultiPolygon parts per district)
  9. Overlap check (expect 0)

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/build_voronoi_districts.py
"""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql


# ---------------------------------------------------------------------------
# Step A: Add columns if missing
# ---------------------------------------------------------------------------

def add_columns() -> None:
    print("\n[B] Ensuring schema columns exist...")
    sqls = [
        """ALTER TABLE skolske_obvody.districts
           ADD COLUMN IF NOT EXISTS geom_voronoi public.geometry(MultiPolygon, 4326)""",
        """ALTER TABLE skolske_obvody.districts
           ADD COLUMN IF NOT EXISTS geom_voronoi_metadata JSONB""",
        """ALTER TABLE skolske_obvody.districts
           ADD COLUMN IF NOT EXISTS geom_sprint_j_backup public.geometry(MultiPolygon, 4326)""",
    ]
    for sql in sqls:
        r = exec_sql(sql)
        if not r.get("ok"):
            raise RuntimeError(f"Column migration failed: {r.get('message')}")
    print("  Columns OK")


# ---------------------------------------------------------------------------
# Step B: Backup current geom
# ---------------------------------------------------------------------------

def backup_current_geom() -> None:
    print("\n[D-backup] Backing up current geom → geom_sprint_j_backup...")
    sql = """
UPDATE skolske_obvody.districts
SET geom_sprint_j_backup = geom
WHERE geom_sprint_j_backup IS NULL
  AND geom IS NOT NULL
  AND municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')
"""
    r = exec_sql(sql)
    if not r.get("ok"):
        print(f"  WARN: backup failed: {r.get('message')}")
    else:
        print("  Backup OK")


# ---------------------------------------------------------------------------
# Step C: PostGIS-native Voronoi tessellation + write geom_voronoi
# ---------------------------------------------------------------------------

VORONOI_UPDATE_SQL = """
WITH pts AS (
  SELECT hg.district_id, hg.geom
  FROM skolske_obvody.house_geocodes hg
  WHERE hg.valid = true AND hg.geom IS NOT NULL
  UNION ALL
  SELECT sg.district_id, sg.geom
  FROM skolske_obvody.street_geocodes sg
  WHERE sg.geom IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM skolske_obvody.vzn_street_ranges vsr
      WHERE vsr.district_id = sg.district_id
        AND vsr.street = sg.street
        AND vsr.range_type = 'all'
    )
),
presov_boundary AS (
  SELECT geom FROM skolske_obvody.municipalities WHERE slug = 'presov'
),
vor_cells AS (
  -- Generate one Voronoi cell per input point, envelope = Prešov boundary
  SELECT (public.ST_Dump(public.ST_VoronoiPolygons(
    public.ST_Collect(pts.geom),
    0.0,
    (SELECT geom FROM presov_boundary)
  ))).geom AS cell_geom
  FROM pts
),
cells_with_district AS (
  -- Assign each cell to the district whose input point falls inside it
  SELECT vc.cell_geom,
         (SELECT p.district_id FROM pts p
          WHERE public.ST_Within(p.geom, vc.cell_geom) LIMIT 1) AS district_id
  FROM vor_cells vc
),
grouped AS (
  -- Union all cells per district, clip to Prešov boundary
  SELECT district_id,
         public.ST_Multi(
           public.ST_Intersection(
             public.ST_Union(cell_geom),
             (SELECT geom FROM presov_boundary)
           )
         ) AS geom_voronoi,
         COUNT(*) AS cell_count
  FROM cells_with_district
  WHERE district_id IS NOT NULL
  GROUP BY district_id
)
UPDATE skolske_obvody.districts d
SET geom_voronoi = grouped.geom_voronoi,
    geom_voronoi_metadata = jsonb_build_object(
      'method', 'postgis_voronoi_tessellation',
      'cell_count', grouped.cell_count,
      'created_at', now()
    )
FROM grouped
WHERE d.id = grouped.district_id
"""


def build_and_write_voronoi() -> None:
    print("\n[C] Building PostGIS Voronoi + writing geom_voronoi...")
    r = exec_sql(VORONOI_UPDATE_SQL)
    if not r.get("ok"):
        raise RuntimeError(f"Voronoi build failed: {r.get('message')}")
    print("  geom_voronoi written to all districts OK")


# ---------------------------------------------------------------------------
# Step D: Promote Voronoi → geom
# ---------------------------------------------------------------------------

def promote_voronoi() -> None:
    print("\n[D] Promoting geom_voronoi → geom (confidence=high, quality=9)...")
    sql = """
UPDATE skolske_obvody.districts
SET geom = geom_voronoi,
    geometry_confidence = 'high',
    geometry_quality = 9
WHERE municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')
  AND geom_voronoi IS NOT NULL
"""
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"Promote failed: {r.get('message')}")
    print("  Promote OK")


# ---------------------------------------------------------------------------
# Step E: Island report (disconnected polygon parts per district)
# ---------------------------------------------------------------------------

def island_report() -> dict:
    print("\n[C-islands] Island (disconnected polygon parts) report:")
    rows = query_sql("""
        SELECT d.name,
               public.ST_NumGeometries(d.geom_voronoi) AS island_count,
               (d.geom_voronoi_metadata->>'cell_count')::int AS cells
        FROM skolske_obvody.districts d
        WHERE d.municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')
          AND d.geom_voronoi IS NOT NULL
        ORDER BY public.ST_NumGeometries(d.geom_voronoi) DESC
    """)

    print(f"  {'District':<55} {'Cells':>6} {'Islands':>8}")
    print("  " + "-" * 73)

    multi_poly = []
    for r in rows:
        name = (r.get("name") or "?")[:54]
        cells = r.get("cells") or "?"
        islands = r.get("island_count") or 1
        flag = " ⚠ ISLANDS" if islands > 1 else ""
        print(f"  {name:<55} {str(cells):>6} {islands:>8}{flag}")
        if islands > 1:
            multi_poly.append((r.get("name", "?"), islands))

    if multi_poly:
        print(f"\n  Districts with disconnected parts: {len(multi_poly)}")
        for name, cnt in multi_poly:
            print(f"    - {name}: {cnt} parts")
    else:
        print("\n  All districts are single connected polygons.")

    return {"districts_with_islands": len(multi_poly), "details": multi_poly}


# ---------------------------------------------------------------------------
# Step F: Overlap check
# ---------------------------------------------------------------------------

def check_overlaps() -> dict:
    print("\n[E] Post-Voronoi overlap check...")
    sql = """
SELECT count(*) AS n,
       COALESCE(sum(public.ST_Area(public.ST_Transform(
         public.ST_Intersection(d1.geom, d2.geom), 32634))), 0) AS total_area_m2
FROM skolske_obvody.districts d1, skolske_obvody.districts d2
WHERE d1.id < d2.id
  AND d1.municipality_id = d2.municipality_id
  AND public.ST_Intersects(d1.geom, d2.geom)
  AND public.ST_Area(public.ST_Transform(
    public.ST_Intersection(d1.geom, d2.geom), 32634)) > 1
  AND d1.municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')
"""
    try:
        rows = query_sql(sql)
        n = int(rows[0]["n"]) if rows else -1
        area = float(rows[0]["total_area_m2"]) if rows else 0.0
        ok = n == 0
        status = "PASS (0 overlaps)" if ok else f"FAIL ({n} pairs, {area / 1_000_000:.2f} km²)"
        print(f"  Result: {status}")
        return {"pairs": n, "total_area_m2": area, "ok": ok}
    except Exception as ex:
        print(f"  WARN: Overlap check error: {ex}")
        return {"pairs": -1, "total_area_m2": 0.0, "ok": False}


# ---------------------------------------------------------------------------
# Step G: Per-district stats
# ---------------------------------------------------------------------------

def per_district_stats() -> list[dict]:
    return query_sql("""
        SELECT d.name,
               (d.geom_voronoi_metadata->>'cell_count')::int AS cells,
               public.ST_NumGeometries(d.geom_voronoi) AS islands,
               round(public.ST_Area(public.ST_Transform(d.geom_voronoi, 32634))::numeric / 1000000, 2) AS area_km2
        FROM skolske_obvody.districts d
        WHERE d.municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')
          AND d.geom_voronoi IS NOT NULL
        ORDER BY d.name
    """)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    validate_config()

    print("=" * 64)
    print("Sprint K — Voronoi Tessellation Districts (PostGIS-native)")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 64)

    # A: Ensure columns exist
    add_columns()

    # B: Backup
    backup_current_geom()

    # C: Build + write Voronoi (PostGIS ST_VoronoiPolygons)
    build_and_write_voronoi()

    # D: Promote → geom
    promote_voronoi()

    # C-islands: Island report
    island_stats = island_report()

    # E: Overlap check
    overlap = check_overlaps()

    # Per-district table
    print("\n  Per-district Voronoi stats:")
    stats = per_district_stats()
    total_cells = 0
    for r in stats:
        name = (r.get("name") or "?")[:54]
        cells = r.get("cells") or 0
        islands = r.get("islands") or 1
        area = r.get("area_km2") or 0
        total_cells += cells
        print(f"  {name:<55} cells={cells:>4} islands={islands} area={area:.2f} km²")

    print("\n" + "=" * 64)
    print("SPRINT K SUMMARY")
    print("=" * 64)
    print(f"Districts:         {len(stats)}")
    print(f"Total Voronoi cells: {total_cells}")
    print(f"Islands detected:  {island_stats['districts_with_islands']} districts with >1 polygon")
    print(f"Overlap pairs:     {overlap['pairs']} (expected: 0)")
    print(f"Overlap area:      {overlap['total_area_m2'] / 1_000_000:.4f} km² (expected: 0)")
    print(f"Overlap check:     {'PASS' if overlap['ok'] else 'FAIL'}")
    print(f"\nFinished: {datetime.now().isoformat()}")

    if not overlap["ok"]:
        print("\nWARN: Non-zero overlaps detected. Check district geometries.")
        sys.exit(1)


if __name__ == "__main__":
    main()
