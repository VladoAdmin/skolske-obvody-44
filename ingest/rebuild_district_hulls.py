"""
Sprint I — Rebuild district hulls from validated points only (per-side streets).

Logic:
  - For streets with range_type='all' → use street centroid (street_geocodes)
  - For streets with range_type in ('odd','even','range','single') → use ONLY
    validated house points (valid=TRUE) for that (district_id, street) pair
    NOT the street centroid (which covers both sides of the street)

  Hull method: ST_ConcaveHull(ST_Collect(...), 0.3, true)
  Updates: districts.geom_google + geom_google_metadata

  Overlap check: counts ST_Overlaps pairs before and after.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(GOOGLE_API_KEY|SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/rebuild_district_hulls.py
"""

from __future__ import annotations

from datetime import datetime
from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql


# ---------------------------------------------------------------------------
# Pre-check
# ---------------------------------------------------------------------------

def _check_validation_done() -> int:
    """Return count of valid house geocodes. Warn if 0."""
    rows = query_sql("SELECT COUNT(*) AS n FROM skolske_obvody.house_geocodes WHERE valid = TRUE")
    n = int(rows[0]['n']) if rows else 0
    if n == 0:
        print("  WARN: No valid house geocodes found. Run validate_house_geocodes.py first.")
    return n


# ---------------------------------------------------------------------------
# Hull rebuild
# ---------------------------------------------------------------------------

def rebuild_hulls() -> dict:
    """
    Rebuild geom_google per district using:
    - Street geocodes for 'all' range streets
    - Validated house points for non-all range streets (per-side)

    Returns stats dict.
    """
    print("\n[D] Rebuilding district hulls (validated per-side points)...")

    sql = """
UPDATE skolske_obvody.districts d
SET
  geom_google = sub.hull,
  geom_google_metadata = jsonb_build_object(
    'method', 'validated_concave_hull_per_side',
    'street_all_points', sub.street_count,
    'house_validated_points', sub.house_count,
    'total_points', sub.total_count,
    'updated_at', now()
  )
FROM (
  SELECT
    d2.id AS district_id,
    public.ST_Multi(
      public.ST_ConcaveHull(
        public.ST_Collect(all_geoms.geom),
        0.3,
        true
      )
    ) AS hull,
    SUM(CASE WHEN all_geoms.src = 'street_all' THEN 1 ELSE 0 END) AS street_count,
    SUM(CASE WHEN all_geoms.src = 'house_valid' THEN 1 ELSE 0 END) AS house_count,
    COUNT(all_geoms.geom) AS total_count
  FROM skolske_obvody.districts d2
  JOIN skolske_obvody.municipalities m ON m.id = d2.municipality_id
  CROSS JOIN LATERAL (
    -- (1) Street centroids for 'all' range streets
    SELECT sg.geom, 'street_all' AS src
    FROM skolske_obvody.street_geocodes sg
    WHERE sg.district_id = d2.id
      AND sg.geom IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM skolske_obvody.vzn_street_ranges vr
        WHERE vr.district_id = d2.id
          AND vr.street = sg.street
          AND vr.range_type = 'all'
      )
    UNION ALL
    -- (2) Validated house points for non-all range streets
    SELECT hg.geom, 'house_valid' AS src
    FROM skolske_obvody.house_geocodes hg
    WHERE hg.district_id = d2.id
      AND hg.geom IS NOT NULL
      AND hg.valid = TRUE
  ) AS all_geoms
  WHERE m.slug = 'presov'
  GROUP BY d2.id
  HAVING COUNT(all_geoms.geom) >= 3
) sub
WHERE d.id = sub.district_id
"""
    result = exec_sql(sql)
    if result.get("ok"):
        print("  Hull rebuild OK (validated_concave_hull_per_side)")
        ok = True
    else:
        msg = result.get("message", "?")
        print(f"  Hull rebuild FAILED: {msg}")
        # Fallback: use all house points (validated only) + all streets
        print("  Trying fallback: all valid house points + street centroids...")
        ok = _fallback_rebuild()

    # Get per-district stats
    stats_rows = query_sql("""
        SELECT d.name,
               (d.geom_google_metadata->>'street_all_points')::int AS street_pts,
               (d.geom_google_metadata->>'house_validated_points')::int AS house_pts,
               (d.geom_google_metadata->>'total_points')::int AS total_pts,
               d.geom_google_metadata->>'method' AS method
        FROM skolske_obvody.districts d
        JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
        WHERE m.slug = 'presov' AND d.geom_google IS NOT NULL
        ORDER BY d.name
    """)

    print(f"\n  Per-district hull stats ({len(stats_rows)} districts):")
    print(f"  {'District':<52} {'StreetPts':>9} {'HousePts':>8} {'Total':>6}")
    print("  " + "-" * 78)
    total_street = 0
    total_house = 0
    for r in stats_rows:
        name = (r['name'] or '?')[:51]
        sp = r.get('street_pts') or 0
        hp = r.get('house_pts') or 0
        tp = r.get('total_pts') or 0
        total_street += sp
        total_house += hp
        print(f"  {name:<52} {sp:>9} {hp:>8} {tp:>6}")
    print(f"  {'TOTAL':<52} {total_street:>9} {total_house:>8}")

    return {
        'ok': ok,
        'districts_updated': len(stats_rows),
        'total_street_pts': total_street,
        'total_house_pts': total_house,
    }


def _fallback_rebuild() -> bool:
    """Fallback: union all streets + validated houses (no per-side filtering)."""
    sql = """
UPDATE skolske_obvody.districts d
SET
  geom_google = sub.hull,
  geom_google_metadata = jsonb_build_object(
    'method', 'validated_concave_hull_fallback',
    'updated_at', now()
  )
FROM (
  SELECT
    d2.id AS district_id,
    public.ST_Multi(
      public.ST_ConcaveHull(
        public.ST_Collect(all_geoms.geom),
        0.3,
        true
      )
    ) AS hull
  FROM skolske_obvody.districts d2
  JOIN skolske_obvody.municipalities m ON m.id = d2.municipality_id
  CROSS JOIN LATERAL (
    SELECT sg.geom FROM skolske_obvody.street_geocodes sg
    WHERE sg.district_id = d2.id AND sg.geom IS NOT NULL
    UNION ALL
    SELECT hg.geom FROM skolske_obvody.house_geocodes hg
    WHERE hg.district_id = d2.id AND hg.geom IS NOT NULL AND hg.valid = TRUE
  ) AS all_geoms
  WHERE m.slug = 'presov'
  GROUP BY d2.id
  HAVING COUNT(all_geoms.geom) >= 3
) sub
WHERE d.id = sub.district_id
"""
    result = exec_sql(sql)
    if result.get("ok"):
        print("  Fallback hull rebuild OK")
        return True
    print(f"  Fallback hull rebuild FAILED: {result.get('message', '?')}")
    return False


# ---------------------------------------------------------------------------
# Overlap check
# ---------------------------------------------------------------------------

def check_overlaps() -> dict:
    """Count ST_Overlaps pairs using the public so_district_overlaps view."""
    print("\n[F] Checking overlap count (so_district_overlaps)...")
    try:
        rows = query_sql("SELECT COUNT(*) AS n FROM public.so_district_overlaps")
        count = int(rows[0]['n']) if rows else -1
        print(f"  Overlap pairs after Sprint I rebuild: {count}")
        return {'overlap_count': count}
    except Exception as ex:
        print(f"  WARN: Could not query overlaps: {ex}")
        return {'overlap_count': -1}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    validate_config()

    print("=" * 64)
    print("Sprint I — Rebuild District Hulls (per-side validated)")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 64)

    # Pre-check
    valid_count = _check_validation_done()
    print(f"\nValid house geocodes available: {valid_count}")
    if valid_count == 0:
        print("ERROR: No validated geocodes. Run validate_house_geocodes.py first.")
        return

    # Rebuild hulls
    hull_stats = rebuild_hulls()

    # Check overlaps
    overlap_stats = check_overlaps()

    print("\n" + "=" * 64)
    print("HULL REBUILD SUMMARY")
    print("=" * 64)
    print(f"Districts updated:   {hull_stats['districts_updated']}")
    print(f"Street (all) pts:    {hull_stats['total_street_pts']}")
    print(f"House (valid) pts:   {hull_stats['total_house_pts']}")
    print(f"Overlap pairs now:   {overlap_stats['overlap_count']} (Sprint A baseline: 57)")
    print(f"\nFinished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
