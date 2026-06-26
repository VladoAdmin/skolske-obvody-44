"""
Sprint L2 — Clean Voronoi islands: drop empty cells + connect islands via corridors.

Steps:
  (A) Drop empty Voronoi cells (0 addresses) per district.
      - Rebuild geom_voronoi from non-empty polygons.
      - If ALL cells are empty → keep the largest cell (don't destroy the district).
      - Update geom_voronoi_metadata with cleaned_at + dropped_empty_cells.

  (B) Connect remaining islands to main body via corridor.
      - Main body = largest polygon by area.
      - For each non-main polygon (island):
        * ST_ShortestLine between island and main body.
        * Buffer 50 m around line → check for house_geocodes of OTHER districts.
        * If no blocking addresses → add 30 m corridor (ST_Buffer(line, 30m)),
          union with geom_voronoi → island is connected.
        * If blocked → flag island as possible_vzn_anomaly.

  (C) Update district_islands table: add status column + re-populate.

  (D) Overlap check after corridors.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/clean_voronoi_islands.py
"""

from __future__ import annotations

import sys
import json
from datetime import datetime

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql


# ---------------------------------------------------------------------------
# Step C (pre-work): Add status + blocking_districts columns to district_islands
# ---------------------------------------------------------------------------

def add_island_columns() -> None:
    print("\n[pre-C] Adding status/blocking_districts columns to district_islands...")
    sqls = [
        "ALTER TABLE skolske_obvody.district_islands ADD COLUMN IF NOT EXISTS status TEXT",
        "ALTER TABLE skolske_obvody.district_islands ADD COLUMN IF NOT EXISTS blocking_districts UUID[]",
        "ALTER TABLE skolske_obvody.district_islands ADD COLUMN IF NOT EXISTS street_count INT",
        "ALTER TABLE skolske_obvody.district_islands ADD COLUMN IF NOT EXISTS house_count INT",
    ]
    for sql in sqls:
        r = exec_sql(sql)
        if not r.get("ok"):
            raise RuntimeError(f"Column migration failed: {r.get('message')}")
    print("  Columns OK")


# ---------------------------------------------------------------------------
# Step A: Drop empty Voronoi cells, rebuild geom_voronoi
# ---------------------------------------------------------------------------

DROP_EMPTY_SQL = """
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov'
),
dumped AS (
  SELECT
    d.id AS district_id,
    (public.ST_Dump(d.geom_voronoi)).path[1] - 1 AS poly_idx,
    (public.ST_Dump(d.geom_voronoi)).geom        AS poly_geom
  FROM skolske_obvody.districts d
  WHERE d.municipality_id = (SELECT id FROM presov)
    AND d.geom_voronoi IS NOT NULL
),
with_addr_count AS (
  SELECT
    du.district_id,
    du.poly_idx,
    du.poly_geom,
    COUNT(hg.id) AS address_count,
    public.ST_Area(du.poly_geom) AS poly_area
  FROM dumped du
  LEFT JOIN skolske_obvody.house_geocodes hg
    ON hg.district_id = du.district_id
    AND hg.valid = true
    AND hg.geom IS NOT NULL
    AND public.ST_Contains(du.poly_geom, hg.geom)
  GROUP BY du.district_id, du.poly_idx, du.poly_geom
),
kept AS (
  -- Keep non-empty cells; if district has ALL empty cells, keep the largest one
  SELECT wac.district_id, wac.poly_geom, wac.address_count, wac.poly_area
  FROM with_addr_count wac
  WHERE wac.address_count > 0
  UNION ALL
  -- fallback: all-empty district → keep largest polygon only
  SELECT wac.district_id, wac.poly_geom, wac.address_count, wac.poly_area
  FROM with_addr_count wac
  WHERE wac.district_id NOT IN (
    SELECT DISTINCT district_id FROM with_addr_count WHERE address_count > 0
  )
    AND wac.poly_area = (
      SELECT MAX(w2.poly_area)
      FROM with_addr_count w2
      WHERE w2.district_id = wac.district_id
    )
),
counts AS (
  SELECT
    district_id,
    COUNT(*) FILTER (WHERE address_count = 0) AS dropped_count,
    COUNT(*) AS remaining_count
  FROM with_addr_count
  GROUP BY district_id
),
rebuilt AS (
  SELECT
    k.district_id,
    public.ST_Multi(public.ST_Union(k.poly_geom)) AS new_geom,
    c.dropped_count,
    c.remaining_count
  FROM kept k
  JOIN counts c ON c.district_id = k.district_id
  GROUP BY k.district_id, c.dropped_count, c.remaining_count
)
UPDATE skolske_obvody.districts d
SET geom_voronoi = rebuilt.new_geom,
    geom_voronoi_metadata = COALESCE(d.geom_voronoi_metadata, '{}'::jsonb)
      || jsonb_build_object(
           'cleaned_at', now(),
           'dropped_empty_cells', rebuilt.dropped_count,
           'remaining_cells', rebuilt.remaining_count
         )
FROM rebuilt
WHERE d.id = rebuilt.district_id
"""


def drop_empty_cells() -> list[dict]:
    """Drop empty Voronoi cells. Returns per-district drop summary."""
    print("\n[A] Dropping empty Voronoi cells...")

    # Snapshot counts before
    before = query_sql("""
        SELECT d.id, d.name,
               public.ST_NumGeometries(d.geom_voronoi) AS poly_count_before
        FROM skolske_obvody.districts d
        WHERE d.municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug='presov')
          AND d.geom_voronoi IS NOT NULL
        ORDER BY d.name
    """)
    before_map = {r["id"]: r for r in before}

    r = exec_sql(DROP_EMPTY_SQL)
    if not r.get("ok"):
        raise RuntimeError(f"drop_empty_cells failed: {r.get('message')}")
    print("  Empty cells dropped OK")

    # Snapshot counts after
    after = query_sql("""
        SELECT d.id, d.name,
               public.ST_NumGeometries(d.geom_voronoi) AS poly_count_after,
               (d.geom_voronoi_metadata->>'dropped_empty_cells')::int AS dropped
        FROM skolske_obvody.districts d
        WHERE d.municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug='presov')
          AND d.geom_voronoi IS NOT NULL
        ORDER BY d.name
    """)

    summary = []
    for a in after:
        b = before_map.get(a["id"], {})
        dropped = int(a.get("dropped") or 0)
        if dropped > 0:
            summary.append({
                "id": a["id"],
                "name": a["name"],
                "poly_before": b.get("poly_count_before", "?"),
                "poly_after": a["poly_count_after"],
                "dropped": dropped,
            })

    print(f"\n  Districts with dropped cells: {len(summary)}")
    for s in summary:
        print(f"    {s['name'][:55]:<55} {s['poly_before']}→{s['poly_after']} polys (dropped {s['dropped']})")

    return summary


# ---------------------------------------------------------------------------
# Step B: Connect islands via corridors
# ---------------------------------------------------------------------------

def get_districts_with_islands() -> list[dict]:
    """Return districts that still have >1 polygon after clean."""
    return query_sql("""
        SELECT d.id, d.name,
               public.ST_NumGeometries(d.geom_voronoi) AS poly_count
        FROM skolske_obvody.districts d
        WHERE d.municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug='presov')
          AND d.geom_voronoi IS NOT NULL
          AND public.ST_NumGeometries(d.geom_voronoi) > 1
        ORDER BY public.ST_NumGeometries(d.geom_voronoi) DESC, d.name
    """)


def _save_voronoi_snapshot(district_id: str) -> str | None:
    """Get current geom_voronoi as WKT for rollback."""
    rows = query_sql(f"""
        SELECT public.ST_AsText(geom_voronoi) AS wkt
        FROM skolske_obvody.districts
        WHERE id = '{district_id}'
    """)
    return rows[0]["wkt"] if rows else None


def _restore_voronoi_snapshot(district_id: str, wkt: str) -> None:
    """Restore geom_voronoi from WKT snapshot."""
    exec_sql(f"""
        UPDATE skolske_obvody.districts
        SET geom_voronoi = public.ST_GeomFromText($_wkt_${wkt}$_wkt_$, 4326)
        WHERE id = '{district_id}'
    """)


def _check_geom_voronoi_overlaps_neighbors(district_id: str) -> tuple[bool, list]:
    """
    Check if current geom_voronoi of district overlaps with any neighbor.
    Returns (has_overlap: bool, blocking_district_ids: list).
    """
    rows = query_sql(f"""
        WITH target AS (
            SELECT geom_voronoi AS g, municipality_id
            FROM skolske_obvody.districts
            WHERE id = '{district_id}'
        ),
        neighbors AS (
            SELECT d2.id AS neighbor_id
            FROM skolske_obvody.districts d2
            WHERE d2.municipality_id = (SELECT municipality_id FROM target)
              AND d2.id != '{district_id}'
              AND d2.geom IS NOT NULL
              AND public.ST_Intersects((SELECT g FROM target), d2.geom)
              AND public.ST_Area(public.ST_Transform(
                  public.ST_Intersection((SELECT g FROM target), d2.geom), 32634)) > 1
        )
        SELECT
          COALESCE(bool_or(true), false) AS has_overlap,
          array_agg(DISTINCT neighbor_id) FILTER (WHERE neighbor_id IS NOT NULL) AS blocking_ids
        FROM neighbors
    """)
    if not rows:
        return False, []
    has_overlap = rows[0].get("has_overlap") or False
    blocking_ids = rows[0].get("blocking_ids") or []
    return has_overlap, blocking_ids


def connect_island_corridor(district_id: str, district_name: str) -> dict:
    """
    For one district: try to connect all non-main islands to the main body.
    Returns dict with connected + anomaly counts.

    Checks both:
    1. Whether the corridor line passes through houses of other districts (50m buffer check).
    2. Whether the corridor polygon itself would cause geometry overlap with a neighbor.
    If either is true → flag as VZN anomaly, skip corridor.
    """
    # Get all individual polygons with their index and area
    polys = query_sql(f"""
        SELECT
            (public.ST_Dump(d.geom_voronoi)).path[1] - 1 AS poly_idx,
            public.ST_Area(public.ST_Transform(
                (public.ST_Dump(d.geom_voronoi)).geom, 32634)) AS area_m2
        FROM skolske_obvody.districts d
        WHERE d.id = '{district_id}'
        ORDER BY area_m2 DESC
    """)

    if len(polys) <= 1:
        return {"connected": 0, "anomaly": 0, "anomaly_details": []}

    connected = 0
    anomalies = []

    for poly in polys[1:]:
        island_idx = poly["poly_idx"]

        # Check 1: houses of other districts in 50m corridor buffer
        check = query_sql(f"""
            WITH main_poly AS (
                SELECT (public.ST_Dump(d.geom_voronoi)).geom AS g
                FROM skolske_obvody.districts d
                WHERE d.id = '{district_id}'
                ORDER BY public.ST_Area(public.ST_Transform(
                    (public.ST_Dump(d.geom_voronoi)).geom, 32634)) DESC
                LIMIT 1
            ),
            island_poly AS (
                SELECT (public.ST_Dump(d.geom_voronoi)).geom AS g,
                       (public.ST_Dump(d.geom_voronoi)).path[1] - 1 AS idx
                FROM skolske_obvody.districts d
                WHERE d.id = '{district_id}'
            ),
            island_g AS (
                SELECT g FROM island_poly WHERE idx = {island_idx}
            ),
            corridor_line AS (
                SELECT public.ST_ShortestLine(
                    (SELECT g FROM main_poly),
                    (SELECT g FROM island_g)
                ) AS line
            ),
            corridor_buffer AS (
                SELECT public.ST_Buffer(
                    public.ST_Transform(line, 32634), 50
                ) AS buf
                FROM corridor_line
            ),
            blocking AS (
                SELECT hg.district_id AS blocking_did
                FROM skolske_obvody.house_geocodes hg
                WHERE hg.district_id != '{district_id}'
                  AND hg.valid = true
                  AND hg.geom IS NOT NULL
                  AND public.ST_Intersects(
                      (SELECT buf FROM corridor_buffer),
                      public.ST_Transform(hg.geom, 32634)
                  )
                LIMIT 5
            )
            SELECT
              COALESCE(bool_or(true), false) AS has_blockers,
              array_agg(DISTINCT blocking_did) FILTER (WHERE blocking_did IS NOT NULL) AS blocking_ids
            FROM blocking
        """)

        has_blockers = check[0]["has_blockers"] if check else False
        blocking_ids_addr = check[0].get("blocking_ids") or []

        if has_blockers:
            anomalies.append({
                "island_idx": island_idx,
                "blocking_district_ids": blocking_ids_addr,
                "reason": "houses_in_corridor",
            })
            print(f"      Island {island_idx}: BLOCKED (houses in corridor) → VZN anomaly")
            continue

        # Save snapshot before adding corridor (for rollback if overlap detected)
        snapshot_wkt = _save_voronoi_snapshot(district_id)

        # Apply corridor
        r = exec_sql(f"""
            WITH main_poly AS (
                SELECT (public.ST_Dump(d.geom_voronoi)).geom AS g
                FROM skolske_obvody.districts d
                WHERE d.id = '{district_id}'
                ORDER BY public.ST_Area(public.ST_Transform(
                    (public.ST_Dump(d.geom_voronoi)).geom, 32634)) DESC
                LIMIT 1
            ),
            island_poly AS (
                SELECT (public.ST_Dump(d.geom_voronoi)).geom AS g,
                       (public.ST_Dump(d.geom_voronoi)).path[1] - 1 AS idx
                FROM skolske_obvody.districts d
                WHERE d.id = '{district_id}'
            ),
            island_g AS (
                SELECT g FROM island_poly WHERE idx = {island_idx}
            ),
            corridor AS (
                SELECT public.ST_Transform(
                    public.ST_Buffer(
                        public.ST_Transform(
                            public.ST_ShortestLine(
                                (SELECT g FROM main_poly),
                                (SELECT g FROM island_g)
                            ),
                            32634
                        ),
                        30
                    ),
                    4326
                ) AS corridor_geom
            ),
            new_geom AS (
                SELECT public.ST_Multi(
                    public.ST_Union(d.geom_voronoi, (SELECT corridor_geom FROM corridor))
                ) AS g
                FROM skolske_obvody.districts d
                WHERE d.id = '{district_id}'
            )
            UPDATE skolske_obvody.districts d
            SET geom_voronoi = (SELECT g FROM new_geom),
                geom_voronoi_metadata = COALESCE(d.geom_voronoi_metadata, '{{}}'::jsonb)
                  || jsonb_build_object('last_corridor_added_at', now())
            WHERE d.id = '{district_id}'
        """)
        if not r.get("ok"):
            print(f"      Island {island_idx}: corridor update failed: {r.get('message', '')[:100]}")
            continue

        # Check 2: post-add overlap check — rollback if corridor caused overlap
        overlap_detected, blocking_ids_geom = _check_geom_voronoi_overlaps_neighbors(district_id)
        if overlap_detected:
            # Rollback
            if snapshot_wkt:
                _restore_voronoi_snapshot(district_id, snapshot_wkt)
            anomalies.append({
                "island_idx": island_idx,
                "blocking_district_ids": blocking_ids_geom,
                "reason": "corridor_geom_overlap",
            })
            print(f"      Island {island_idx}: BLOCKED (corridor caused geom overlap, rolled back) → VZN anomaly")
        else:
            connected += 1
            print(f"      Island {island_idx}: CONNECTED via corridor")

    return {
        "connected": connected,
        "anomaly": len(anomalies),
        "anomaly_details": anomalies,
    }


def connect_all_islands() -> dict:
    """Connect islands for all districts with >1 polygon. Returns summary."""
    districts = get_districts_with_islands()
    print(f"\n[B] Connecting islands — {len(districts)} districts with >1 polygon:")

    total_connected = 0
    total_anomaly = 0
    per_district = {}

    for d in districts:
        district_id = d["id"]
        name = d["name"]
        poly_count = d["poly_count"]
        print(f"\n  {name} ({poly_count} polygons):")
        result = connect_island_corridor(district_id, name)
        total_connected += result["connected"]
        total_anomaly += result["anomaly"]
        per_district[district_id] = result
        per_district[district_id]["name"] = name

    print(f"\n  Total connected: {total_connected}, Total anomalies: {total_anomaly}")
    return {
        "total_connected": total_connected,
        "total_anomaly": total_anomaly,
        "per_district": per_district,
    }


# ---------------------------------------------------------------------------
# Step D: Promote cleaned geom_voronoi → geom
# ---------------------------------------------------------------------------

def promote_voronoi() -> None:
    print("\n[D] Promoting cleaned geom_voronoi → geom...")
    sql = """
UPDATE skolske_obvody.districts
SET geom = geom_voronoi
WHERE municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')
  AND geom_voronoi IS NOT NULL
"""
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"Promote failed: {r.get('message')}")
    print("  Promote OK")


# ---------------------------------------------------------------------------
# Step C: Re-populate district_islands with status
# ---------------------------------------------------------------------------

REPOPULATE_SQL = """
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov'
),
dumped AS (
  SELECT
    d.id AS district_id,
    (public.ST_Dump(d.geom_voronoi)).path[1] - 1 AS island_index,
    (public.ST_Dump(d.geom_voronoi)).geom        AS island_geom
  FROM skolske_obvody.districts d
  WHERE d.municipality_id = (SELECT id FROM presov)
    AND d.geom_voronoi IS NOT NULL
),
with_stats AS (
  SELECT
    du.district_id,
    du.island_index,
    round(public.ST_Area(public.ST_Transform(du.island_geom, 5514))::numeric, 1) AS area_m2,
    du.island_geom AS geom,
    array_remove(array_agg(DISTINCT hg.street ORDER BY hg.street), NULL) AS streets,
    array_remove(array_agg(DISTINCT hg.house_number ORDER BY hg.house_number), NULL) AS house_numbers,
    COUNT(hg.id) AS house_count_raw
  FROM dumped du
  LEFT JOIN skolske_obvody.house_geocodes hg
    ON hg.district_id = du.district_id
    AND hg.valid = true
    AND hg.geom IS NOT NULL
    AND public.ST_Contains(du.island_geom, hg.geom)
  GROUP BY du.district_id, du.island_index, du.island_geom
)
INSERT INTO skolske_obvody.district_islands
  (district_id, island_index, area_m2, geom, streets, house_numbers, house_count, street_count)
SELECT district_id, island_index, area_m2, geom,
       streets, house_numbers,
       house_count_raw::int,
       COALESCE(array_length(streets, 1), 0)
FROM with_stats
ON CONFLICT (district_id, island_index) DO UPDATE SET
  area_m2       = EXCLUDED.area_m2,
  geom          = EXCLUDED.geom,
  streets       = EXCLUDED.streets,
  house_numbers = EXCLUDED.house_numbers,
  house_count   = EXCLUDED.house_count,
  street_count  = EXCLUDED.street_count
"""


def repopulate_islands() -> None:
    print("\n[C] Re-populating district_islands table...")
    r = exec_sql(REPOPULATE_SQL)
    if not r.get("ok"):
        raise RuntimeError(f"repopulate_islands failed: {r.get('message')}")
    print("  Re-populated OK")


def update_island_statuses(corridor_result: dict) -> None:
    """Set status on district_islands rows based on corridor results."""
    print("\n[C2] Updating island statuses...")

    per_district = corridor_result.get("per_district", {})

    for district_id, info in per_district.items():
        anomaly_details = info.get("anomaly_details", [])

        # Mark anomaly islands
        for anm in anomaly_details:
            island_idx = anm["island_idx"]
            blocking_ids = anm.get("blocking_district_ids") or []
            blocking_arr = "ARRAY[" + ",".join(f"'{bid}'::uuid" for bid in blocking_ids) + "]" if blocking_ids else "NULL"

            r = exec_sql(f"""
                UPDATE skolske_obvody.district_islands
                SET status = 'unresolved_anomaly',
                    blocking_districts = {blocking_arr}
                WHERE district_id = '{district_id}'
                  AND island_index = {island_idx}
            """)
            if not r.get("ok"):
                print(f"  WARN: status update failed for {district_id}/island {island_idx}: {r.get('message', '')[:80]}")

    # Mark all remaining non-anomaly islands with >0 addresses as connected_to_main
    # (they either were connected or are the main body itself)
    r = exec_sql("""
        UPDATE skolske_obvody.district_islands
        SET status = 'connected_to_main'
        WHERE status IS NULL
          AND COALESCE(house_count, 0) > 0
    """)
    if not r.get("ok"):
        print(f"  WARN: connected_to_main update failed: {r.get('message', '')[:80]}")

    # All still-null rows are single-polygon districts → fine (main body)
    r = exec_sql("""
        UPDATE skolske_obvody.district_islands
        SET status = 'main_body'
        WHERE status IS NULL
    """)
    if not r.get("ok"):
        print(f"  WARN: main_body update failed: {r.get('message', '')[:80]}")

    print("  Statuses updated OK")


# ---------------------------------------------------------------------------
# Overlap check
# ---------------------------------------------------------------------------

def check_overlaps() -> dict:
    print("\n[E] Post-L2 overlap check...")
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
        status = "PASS (0 overlaps)" if ok else f"FAIL ({n} pairs, {area / 1_000_000:.4f} km²)"
        print(f"  Result: {status}")
        return {"pairs": n, "total_area_m2": area, "ok": ok}
    except Exception as ex:
        print(f"  WARN: Overlap check error: {ex}")
        return {"pairs": -1, "total_area_m2": 0.0, "ok": False}


# ---------------------------------------------------------------------------
# Post-L2 island summary
# ---------------------------------------------------------------------------

def final_island_summary() -> list[dict]:
    return query_sql("""
        SELECT d.id, d.name,
               public.ST_NumGeometries(d.geom_voronoi) AS poly_count,
               COUNT(di.id) AS island_count,
               COUNT(di.id) FILTER (WHERE di.status = 'unresolved_anomaly') AS anomaly_count,
               COUNT(di.id) FILTER (WHERE di.status = 'connected_to_main') AS connected_count
        FROM skolske_obvody.districts d
        LEFT JOIN skolske_obvody.district_islands di ON di.district_id = d.id
        WHERE d.municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug='presov')
          AND d.geom_voronoi IS NOT NULL
        GROUP BY d.id, d.name
        ORDER BY poly_count DESC, d.name
    """)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    validate_config()

    print("=" * 70)
    print("Sprint L2 — Clean Voronoi Islands (drop empty + connect corridors)")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    # Pre-work: add columns to district_islands
    add_island_columns()

    # A: Drop empty Voronoi cells
    drop_summary = drop_empty_cells()

    # B: Connect remaining islands via corridors
    corridor_result = connect_all_islands()

    # D: Promote cleaned geom_voronoi → geom
    promote_voronoi()

    # C: Re-populate district_islands + set statuses
    repopulate_islands()
    update_island_statuses(corridor_result)

    # E: Overlap check
    overlap = check_overlaps()

    # Final summary
    print("\n[F] Post-L2 island summary:")
    summary = final_island_summary()
    SMERALOVA_ID = "cddfee4e-fb1d-48c1-bbb5-2626ae415f87"
    for row in summary:
        name = (row.get("name") or "?")[:55]
        poly_count = row.get("poly_count") or 1
        anomaly = int(row.get("anomaly_count") or 0)
        connected = int(row.get("connected_count") or 0)
        flag = ""
        if anomaly:
            flag = f" [ANOMALY x{anomaly}]"
        elif int(poly_count) > 1:
            flag = f" [MULTI poly={poly_count}]"
        print(f"  {name:<55} connected={connected} anomaly={anomaly}{flag}")

    sm = next((r for r in summary if r.get("id") == SMERALOVA_ID), None)

    print("\n" + "=" * 70)
    print("SPRINT L2 SUMMARY")
    print("=" * 70)
    print(f"Districts with dropped empty cells: {len(drop_summary)}")
    total_dropped = sum(s["dropped"] for s in drop_summary)
    print(f"Total empty cells dropped: {total_dropped}")
    print()
    for s in drop_summary:
        print(f"  {s['name'][:55]:<55} dropped={s['dropped']} ({s['poly_before']}→{s['poly_after']} polys)")

    print(f"\nIslands connected via corridor: {corridor_result['total_connected']}")
    print(f"Unresolved anomaly islands:     {corridor_result['total_anomaly']}")

    if sm:
        print(f"\nŠmeralova č. 25 final: {sm['poly_count']} polygon(s)")
    else:
        print("\nŠmeralova č. 25: not found in summary")

    overlap_str = "PASS (0)" if overlap["ok"] else f"FAIL ({overlap['pairs']} pairs, {overlap['total_area_m2'] / 1_000_000:.4f} km2)"
    print(f"\nOverlap check: {overlap_str}")
    print(f"\nFinished: {datetime.now().isoformat()}")

    if not overlap["ok"]:
        print("\nWARN: Corridors caused overlaps! Manual review required.")
        sys.exit(1)


if __name__ == "__main__":
    main()
