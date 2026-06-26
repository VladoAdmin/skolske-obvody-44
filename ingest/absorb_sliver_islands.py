"""
Sliver-island cleanup pass (extends the canonical Voronoi build).

Problem: the Voronoi tessellation (build_voronoi_districts.py) leaves several
districts as MultiPolygons whose extra parts are a MIX of:
  - tiny slivers (geocoding/tessellation artefacts, a few thousand m²), and
  - substantial real splits (e.g. Kúpeľná's 8.6 km² second body, Šrobárova's
    0.58/0.27 twin bodies, Sibírska's 1.5/1.1, Šmeralova's 0.79/0.46/0.30...).

This pass absorbs ONLY the slivers into the adjacent district they share the
longest border with, so the city stays fully tiled (0 gaps, 0 overlaps) and
each sliver's area is preserved (moved, not deleted). Substantial parts are
left untouched — they are surfaced as review flags instead (Task B).

Sliver definition (defensible, conservative):
    area < SLIVER_MAX_KM2 (0.05 km²)  AND  area < SLIVER_MAX_PCT (2%) of the
    district's total area.
A part must satisfy BOTH conditions; a 0.04 km² part that is 30% of a tiny
district is NOT a sliver and is kept.

Safety:
  - Backs up districts.geom → geom_island_backup (fresh column) before writing.
  - After absorption: re-runs the pairwise overlap check (must stay 0) and
    confirms the districts' total area still ≈ Prešov boundary area.
  - If either check fails → restores from geom_island_backup and exits non-zero
    WITHOUT leaving partial state.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/absorb_sliver_islands.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

# --- Sliver thresholds (a part must satisfy BOTH to be absorbed) ---
SLIVER_MAX_KM2 = 0.05   # absolute area ceiling
SLIVER_MAX_PCT = 0.02   # and < 2% of the district's total area

PRESOV = "(SELECT id FROM skolske_obvody.municipalities WHERE slug = $$presov$$)"


# ---------------------------------------------------------------------------
# Step 0: backup column + snapshot
# ---------------------------------------------------------------------------

def ensure_backup_column() -> None:
    print("\n[0] Ensuring geom_island_backup column exists...")
    r = exec_sql(
        "ALTER TABLE skolske_obvody.districts "
        "ADD COLUMN IF NOT EXISTS geom_island_backup public.geometry(MultiPolygon, 4326)"
    )
    if not r.get("ok"):
        raise RuntimeError(f"Column add failed: {r.get('message')}")
    print("  Column OK")


def backup_geom() -> None:
    """Fresh backup: overwrite geom_island_backup with current geom for all
    Prešov districts (so re-runs always snapshot the live state)."""
    print("\n[0b] Backing up current geom → geom_island_backup...")
    r = exec_sql(f"""
        UPDATE skolske_obvody.districts
        SET geom_island_backup = geom
        WHERE municipality_id = {PRESOV}
          AND geom IS NOT NULL
    """)
    if not r.get("ok"):
        raise RuntimeError(f"Backup failed: {r.get('message')}")
    print("  Backup OK")


def restore_geom() -> None:
    print("\n[!] Restoring geom from geom_island_backup...")
    r = exec_sql(f"""
        UPDATE skolske_obvody.districts
        SET geom = geom_island_backup
        WHERE municipality_id = {PRESOV}
          AND geom_island_backup IS NOT NULL
    """)
    if not r.get("ok"):
        raise RuntimeError(f"RESTORE FAILED: {r.get('message')}")
    print("  Restore OK")


# ---------------------------------------------------------------------------
# Step 1: identify sliver parts + their longest-border neighbour
# ---------------------------------------------------------------------------

SLIVER_QUERY = f"""
WITH parts AS (
  SELECT d.id AS did, d.name,
    (public.ST_Dump(d.geom)).path[1] - 1 AS idx,
    (public.ST_Dump(d.geom)).geom AS g
  FROM skolske_obvody.districts d
  WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
),
withtot AS (
  SELECT p.*,
    public.ST_Area(public.ST_Transform(p.g, 32634)) / 1e6 AS area_km2,
    SUM(public.ST_Area(public.ST_Transform(p.g, 32634)) / 1e6)
      OVER (PARTITION BY p.did) AS tot_km2,
    COUNT(*) OVER (PARTITION BY p.did) AS nparts
  FROM parts p
)
SELECT w.did, w.name, w.idx,
  round(w.area_km2::numeric, 4) AS area_km2,
  round((100 * w.area_km2 / w.tot_km2)::numeric, 3) AS pct,
  (SELECT d2.id FROM skolske_obvody.districts d2
     WHERE d2.id <> w.did AND d2.municipality_id = {PRESOV}
       AND d2.geom IS NOT NULL
       AND public.ST_Intersects(w.g, d2.geom)
     ORDER BY public.ST_Length(public.ST_Transform(
       public.ST_Intersection(public.ST_Boundary(w.g), d2.geom), 32634)) DESC NULLS LAST
     LIMIT 1) AS neighbor_id,
  (SELECT d2.name FROM skolske_obvody.districts d2
     WHERE d2.id <> w.did AND d2.municipality_id = {PRESOV}
       AND d2.geom IS NOT NULL
       AND public.ST_Intersects(w.g, d2.geom)
     ORDER BY public.ST_Length(public.ST_Transform(
       public.ST_Intersection(public.ST_Boundary(w.g), d2.geom), 32634)) DESC NULLS LAST
     LIMIT 1) AS neighbor_name
FROM withtot w
WHERE w.nparts > 1
  AND w.area_km2 < {SLIVER_MAX_KM2}
  AND (w.area_km2 / w.tot_km2) < {SLIVER_MAX_PCT}
ORDER BY w.name, w.area_km2 DESC
"""


def find_slivers() -> list[dict]:
    print(
        f"\n[1] Identifying slivers (area < {SLIVER_MAX_KM2} km² AND "
        f"< {SLIVER_MAX_PCT * 100:.0f}% of district)..."
    )
    rows = query_sql(SLIVER_QUERY)
    for r in rows:
        print(
            f"    {(r['name'] or '?')[:38]:<38} idx={r['idx']} "
            f"{r['area_km2']} km² ({r['pct']}%)  →  {(r['neighbor_name'] or '??')[:38]}"
        )
    print(f"  Total slivers to absorb: {len(rows)}")
    no_neighbor = [r for r in rows if not r.get("neighbor_id")]
    if no_neighbor:
        raise RuntimeError(
            f"{len(no_neighbor)} sliver(s) have NO adjacent neighbour to absorb "
            f"into — aborting (would create a gap). Parts: "
            + ", ".join(f"{r['name']}#{r['idx']}" for r in no_neighbor)
        )
    return rows


# ---------------------------------------------------------------------------
# Step 2: absorb each sliver into its longest-border neighbour
# ---------------------------------------------------------------------------

def _rebuild_geoms(slivers: list[dict]) -> None:
    """Rebuild geom per affected district:
      - owner district: union of its parts EXCEPT the absorbed sliver indices
      - neighbour district: its geom UNION the sliver polygons it received
    Done as one SQL statement using a VALUES mapping so the write is atomic.
    """
    # Map: owner_did -> set(absorbed idx); neighbour_did -> list of (owner_did, idx)
    absorbed_by_owner: dict[str, list[int]] = {}
    received_by_neighbor: dict[str, list[tuple[str, int]]] = {}
    for s in slivers:
        absorbed_by_owner.setdefault(s["did"], []).append(s["idx"])
        received_by_neighbor.setdefault(s["neighbor_id"], []).append((s["did"], s["idx"]))

    # Build a mapping table (owner_did, idx, target_did) as SQL VALUES.
    mapping_rows = ",\n    ".join(
        f"('{s['did']}'::uuid, {s['idx']}, '{s['neighbor_id']}'::uuid)"
        for s in slivers
    )

    sql = f"""
    WITH mapping(owner_did, idx, target_did) AS (
      VALUES
        {mapping_rows}
    ),
    dumped AS (
      SELECT d.id AS did,
             (public.ST_Dump(d.geom)).path[1] - 1 AS idx,
             (public.ST_Dump(d.geom)).geom AS g
      FROM skolske_obvody.districts d
      WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
    ),
    -- parts that STAY with their owner (not an absorbed sliver)
    kept_parts AS (
      SELECT du.did, du.g
      FROM dumped du
      LEFT JOIN mapping m ON m.owner_did = du.did AND m.idx = du.idx
      WHERE m.owner_did IS NULL
    ),
    -- slivers routed to their target neighbour
    received_parts AS (
      SELECT m.target_did AS did, du.g
      FROM dumped du
      JOIN mapping m ON m.owner_did = du.did AND m.idx = du.idx
    ),
    all_parts AS (
      SELECT did, g FROM kept_parts
      UNION ALL
      SELECT did, g FROM received_parts
    ),
    rebuilt AS (
      SELECT did, public.ST_Multi(public.ST_UnaryUnion(public.ST_Collect(g))) AS new_geom
      FROM all_parts
      GROUP BY did
    )
    UPDATE skolske_obvody.districts d
    SET geom = rebuilt.new_geom,
        -- keep geom_voronoi in sync (the district detail map renders from it)
        geom_voronoi = rebuilt.new_geom
    FROM rebuilt
    WHERE d.id = rebuilt.did
    """

    print("\n[2] Absorbing slivers into neighbours (atomic geom rebuild)...")
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"Absorption rebuild failed: {r.get('message')}")
    print("  geom rebuilt OK for affected districts")


# ---------------------------------------------------------------------------
# Step 3: safety checks
# ---------------------------------------------------------------------------

def check_overlaps() -> int:
    rows = query_sql(f"""
        SELECT count(*) AS n
        FROM skolske_obvody.districts d1, skolske_obvody.districts d2
        WHERE d1.id < d2.id AND d1.municipality_id = d2.municipality_id
          AND d1.municipality_id = {PRESOV}
          AND public.ST_Intersects(d1.geom, d2.geom)
          AND public.ST_Area(public.ST_Transform(
              public.ST_Intersection(d1.geom, d2.geom), 32634)) > 1
    """)
    return int(rows[0]["n"]) if rows else -1


def total_area_km2() -> float:
    rows = query_sql(f"""
        SELECT COALESCE(SUM(public.ST_Area(public.ST_Transform(geom, 32634))) / 1e6, 0) AS a
        FROM skolske_obvody.districts
        WHERE municipality_id = {PRESOV} AND geom IS NOT NULL
    """)
    return float(rows[0]["a"]) if rows else 0.0


def boundary_area_km2() -> float:
    rows = query_sql(f"""
        SELECT public.ST_Area(public.ST_Transform(geom, 32634)) / 1e6 AS a
        FROM skolske_obvody.municipalities WHERE slug = $$presov$$
    """)
    return float(rows[0]["a"]) if rows else 0.0


def part_counts() -> list[dict]:
    return query_sql(f"""
        SELECT d.name, public.ST_NumGeometries(d.geom) AS parts
        FROM skolske_obvody.districts d
        WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
        ORDER BY parts DESC, d.name
    """)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    validate_config()

    print("=" * 70)
    print("Absorb sliver islands (homogenize where safe)")
    print("=" * 70)

    area_before = total_area_km2()
    boundary = boundary_area_km2()
    overlaps_before = check_overlaps()
    print(f"\nBaseline: districts total {area_before:.4f} km² | "
          f"boundary {boundary:.4f} km² | overlaps {overlaps_before}")

    ensure_backup_column()
    backup_geom()

    slivers = find_slivers()
    if not slivers:
        print("\nNo slivers found — nothing to do.")
        return

    _rebuild_geoms(slivers)

    # Safety re-checks
    overlaps_after = check_overlaps()
    area_after = total_area_km2()
    area_drift = abs(area_after - area_before)
    print(f"\n[3] Safety checks:")
    print(f"  Overlap pairs: {overlaps_after} (must be 0)")
    print(f"  Total area: {area_after:.4f} km² (was {area_before:.4f}, "
          f"boundary {boundary:.4f}, drift {area_drift:.6f})")

    # Absorption only moves area between districts, so total must be preserved
    # to within rounding noise (1 m² ≈ 1e-6 km²; allow 0.001 km² tolerance).
    area_ok = area_drift < 0.001 and abs(area_after - boundary) < 0.001
    overlap_ok = overlaps_after == 0

    if not (area_ok and overlap_ok):
        print("\n!!! SAFETY CHECK FAILED — reverting !!!")
        if not overlap_ok:
            print(f"  overlap pairs = {overlaps_after} (expected 0)")
        if not area_ok:
            print(f"  area drift = {area_drift:.6f} km² / boundary delta "
                  f"{abs(area_after - boundary):.6f} km² (expected ~0)")
        restore_geom()
        # confirm restore
        print(f"  After restore: overlaps={check_overlaps()}, "
              f"area={total_area_km2():.4f} km²")
        sys.exit(1)

    print("\n[4] Post-absorption part counts:")
    for r in part_counts():
        parts = int(r["parts"])
        flag = f"  ⚠ MULTI-PART ({parts})" if parts > 1 else ""
        print(f"  {(r['name'] or '?')[:50]:<50} parts={parts}{flag}")

    multi = [r for r in part_counts() if int(r["parts"]) > 1]
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Slivers absorbed: {len(slivers)}")
    print(f"Overlap pairs after: {overlaps_after} (PASS)" if overlap_ok else "OVERLAP FAIL")
    print(f"Total area: {area_after:.4f} km² ≈ boundary {boundary:.4f} km² (PASS)")
    print(f"Districts still multi-part (→ Task B flags): {len(multi)}")
    for r in multi:
        print(f"  - {r['name']}: {r['parts']} parts")


if __name__ == "__main__":
    main()
