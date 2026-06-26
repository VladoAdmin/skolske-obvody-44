"""
Evidence-less part cleanup pass (Vlado QA backlog, bod 7).

Problem: the street-line rebuild (build_street_districts.py) can leave a district
MultiPolygon with micro-fragment parts that carry NO address evidence — i.e. a
pure tessellation corridor that the VZN never actually assigns any address to.
The area-based sliver pass (absorb_sliver_islands.py) keys on area thresholds, so
it can miss an evidence-less part that happens to sit just above the area ceiling,
and can also touch parts that DO carry addresses.

This pass keys strictly on EVIDENCE, reusing the SAME street/house->part spatial
join the build already uses (build_street_districts.ABSORB_SQL):

    evidence(part) = (# street_geocodes points of this district within the part)
                   + (# valid house_geocodes of this district within the part)

A part is "evidence-less" iff evidence == 0. Because such a part contains no
address (and no VZN street geocode), no address can be misassigned when it is
absorbed — safe by construction, and consistent with the project rule
"only force-merge parts that carry no evidence; never merge parts that carry real
addresses".

Each evidence-less part is absorbed into the adjacent district it shares the
LONGEST border with (identical merge approach to absorb_sliver_islands.py), so
the city stays fully tiled (0 gaps, 0 overlaps) and the part's area is moved, not
deleted.

ANOMALY GUARD (mandatory): an evidence-less part is expected to be a MICRO
fragment. If a candidate part's area exceeds ABSORB_MAX_KM2, that is NOT a safe
sliver — it signals a join/coverage bug (e.g. a substantial real VZN body whose
addresses simply failed to geocode), exactly the case flag_multipart_districts.py
keeps as a review anomaly. In that case this pass REFUSES to apply and exits
non-zero, leaving geom untouched. It never silently merges a large body.

Safety (mirrors absorb_sliver_islands.py exactly):
  - Backs up districts.geom -> geom_evidenceless_backup (fresh column) before any
    write.
  - DRY-RUN FIRST: prints and writes a report file listing every candidate part
    (district name+id, part index, area km2, street count, house count, target
    district), plus totals.
  - Then APPLY (only if no anomaly). After absorption: re-runs the pairwise
    overlap check (must stay 0) and confirms total districts area still
    ~= Prešov boundary area. If either fails -> restore from
    geom_evidenceless_backup and exit non-zero WITHOUT leaving partial state.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/absorb_evidenceless_parts.py            # dry-run + apply (guarded)
    python3 ingest/absorb_evidenceless_parts.py --dry-run  # report only, never writes
"""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

# An evidence-less part is expected to be a micro-fragment. A candidate larger
# than this is treated as a join/coverage ANOMALY (substantial real body that
# failed to geocode), and the pass refuses to apply. 0.10 km² is double the
# sliver ceiling (absorb_sliver_islands SLIVER_MAX_KM2 = 0.05) — generous, but
# anything in km²-scale is unambiguously a real body, not noise.
ABSORB_MAX_KM2 = 0.10

REPORT_PATH = "docs/evidenceless-absorb-report.md"

PRESOV = "(SELECT id FROM skolske_obvody.municipalities WHERE slug = $$presov$$)"


# ---------------------------------------------------------------------------
# Step 0: backup column + snapshot (mirror absorb_sliver_islands.py)
# ---------------------------------------------------------------------------

def ensure_backup_column() -> None:
    print("\n[0] Ensuring geom_evidenceless_backup column exists...")
    r = exec_sql(
        "ALTER TABLE skolske_obvody.districts "
        "ADD COLUMN IF NOT EXISTS geom_evidenceless_backup public.geometry(MultiPolygon, 4326)"
    )
    if not r.get("ok"):
        raise RuntimeError(f"Column add failed: {r.get('message')}")
    print("  Column OK")


def backup_geom() -> None:
    print("\n[0b] Backing up current geom -> geom_evidenceless_backup...")
    r = exec_sql(f"""
        UPDATE skolske_obvody.districts
        SET geom_evidenceless_backup = geom
        WHERE municipality_id = {PRESOV}
          AND geom IS NOT NULL
    """)
    if not r.get("ok"):
        raise RuntimeError(f"Backup failed: {r.get('message')}")
    print("  Backup OK")


def restore_geom() -> None:
    print("\n[!] Restoring geom from geom_evidenceless_backup...")
    r = exec_sql(f"""
        UPDATE skolske_obvody.districts
        SET geom = geom_evidenceless_backup
        WHERE municipality_id = {PRESOV}
          AND geom_evidenceless_backup IS NOT NULL
    """)
    if not r.get("ok"):
        raise RuntimeError(f"RESTORE FAILED: {r.get('message')}")
    print("  Restore OK")


# ---------------------------------------------------------------------------
# Step 1: identify evidence-less parts + their longest-border neighbour
#
# Evidence uses the SAME street/house->part join as build_street_districts.py
# ABSORB_SQL: street_geocodes points + valid house_geocodes points that fall
# WITHIN the part and belong to the part's own district.
# ---------------------------------------------------------------------------

EVIDENCELESS_QUERY = f"""
WITH parts AS (
  SELECT d.id AS did, d.name,
    (public.ST_Dump(d.geom)).path[1] - 1 AS idx,
    (public.ST_Dump(d.geom)).geom AS g,
    public.ST_NumGeometries(d.geom) AS nparts
  FROM skolske_obvody.districts d
  WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
),
scored AS (
  SELECT p.*,
    public.ST_Area(public.ST_Transform(p.g, 32634)) / 1e6 AS area_km2,
    (SELECT count(*) FROM skolske_obvody.street_geocodes sg
       WHERE sg.district_id = p.did AND public.ST_Within(sg.geom, p.g)) AS street_count,
    (SELECT count(*) FROM skolske_obvody.house_geocodes hg
       WHERE hg.district_id = p.did AND hg.valid AND public.ST_Within(hg.geom, p.g)) AS house_count
  FROM parts p
  WHERE p.nparts > 1
)
SELECT s.did, s.name, s.idx,
  round(s.area_km2::numeric, 5) AS area_km2,
  s.street_count, s.house_count,
  (SELECT d2.id FROM skolske_obvody.districts d2
     WHERE d2.id <> s.did AND d2.municipality_id = {PRESOV}
       AND d2.geom IS NOT NULL
       AND public.ST_Intersects(s.g, d2.geom)
     ORDER BY public.ST_Length(public.ST_Transform(
       public.ST_Intersection(public.ST_Boundary(s.g), d2.geom), 32634)) DESC NULLS LAST
     LIMIT 1) AS neighbor_id,
  (SELECT d2.name FROM skolske_obvody.districts d2
     WHERE d2.id <> s.did AND d2.municipality_id = {PRESOV}
       AND d2.geom IS NOT NULL
       AND public.ST_Intersects(s.g, d2.geom)
     ORDER BY public.ST_Length(public.ST_Transform(
       public.ST_Intersection(public.ST_Boundary(s.g), d2.geom), 32634)) DESC NULLS LAST
     LIMIT 1) AS neighbor_name
FROM scored s
WHERE s.street_count = 0 AND s.house_count = 0
ORDER BY s.area_km2 DESC
"""


def find_evidenceless() -> list[dict]:
    print("\n[1] Identifying evidence-less parts (0 street_geocodes + 0 house_geocodes)...")
    rows = query_sql(EVIDENCELESS_QUERY)
    for r in rows:
        print(
            f"    {(r['name'] or '?')[:38]:<38} idx={r['idx']} "
            f"{r['area_km2']} km²  streets={r['street_count']} houses={r['house_count']}"
            f"  →  {(r['neighbor_name'] or '??')[:38]}"
        )
    print(f"  Total evidence-less parts: {len(rows)}")
    return rows


# ---------------------------------------------------------------------------
# Report (always written, before any apply)
# ---------------------------------------------------------------------------

def write_report(rows: list[dict], anomalies: list[dict]) -> None:
    lines: list[str] = []
    lines.append("# Evidence-less district parts — absorb report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")
    lines.append(
        "Evidence join (same as `build_street_districts.py`): a part's evidence = "
        "count of `street_geocodes` points + count of valid `house_geocodes` of the "
        "part's own district that fall WITHIN the part. A part is evidence-less iff "
        "that count is 0."
    )
    lines.append("")
    lines.append(f"Anomaly guard: candidate parts with area > {ABSORB_MAX_KM2} km² are NOT "
                 "absorbed (a km²-scale evidence-less part signals a geocode-coverage bug, "
                 "not a safe micro-fragment).")
    lines.append("")
    lines.append(f"- Candidate evidence-less parts found: **{len(rows)}**")
    lines.append(f"- Anomalous (over area ceiling, refused): **{len(anomalies)}**")
    safe = [r for r in rows if float(r["area_km2"]) <= ABSORB_MAX_KM2]
    lines.append(f"- Safe to absorb: **{len(safe)}**")
    lines.append("")
    lines.append("| district | id | idx | area km² | streets | houses | → target |")
    lines.append("|---|---|---|---:|---:|---:|---|")
    for r in rows:
        flag = " ⚠ANOMALY" if float(r["area_km2"]) > ABSORB_MAX_KM2 else ""
        lines.append(
            f"| {r['name']}{flag} | {r['did']} | {r['idx']} | {r['area_km2']} | "
            f"{r['street_count']} | {r['house_count']} | "
            f"{r['neighbor_name'] or '— (no neighbour)'} |"
        )
    lines.append("")
    if anomalies:
        lines.append("## REFUSED — anomalies (NOT applied)")
        lines.append("")
        lines.append(
            "These parts have zero house_geocodes yet are km²-scale real bodies "
            "(many carry dozens of `street_geocodes` VZN points). Under the canonical "
            "`street_geocodes + house_geocodes` evidence join they are NOT evidence-less; "
            "they only look empty under a house-only join because their addresses failed "
            "to geocode. They are exactly the substantial VZN splits that "
            "`flag_multipart_districts.py` keeps as review anomalies. The pass refuses to "
            "merge them."
        )
        lines.append("")
        for r in anomalies:
            lines.append(
                f"- **{r['name']}** idx={r['idx']} — {r['area_km2']} km², "
                f"streets={r['street_count']}, houses={r['house_count']}"
            )
        lines.append("")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[report] Written to {REPORT_PATH}")


# ---------------------------------------------------------------------------
# Step 2: absorb each evidence-less part into its longest-border neighbour
# (atomic geom rebuild — identical approach to absorb_sliver_islands.py)
# ---------------------------------------------------------------------------

def _rebuild_geoms(parts: list[dict]) -> None:
    mapping_rows = ",\n    ".join(
        f"('{s['did']}'::uuid, {s['idx']}, '{s['neighbor_id']}'::uuid)"
        for s in parts
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
    kept_parts AS (
      SELECT du.did, du.g
      FROM dumped du
      LEFT JOIN mapping m ON m.owner_did = du.did AND m.idx = du.idx
      WHERE m.owner_did IS NULL
    ),
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
    print("\n[2] Absorbing evidence-less parts into neighbours (atomic geom rebuild)...")
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"Absorption rebuild failed: {r.get('message')}")
    print("  geom rebuilt OK for affected districts")


# ---------------------------------------------------------------------------
# Step 3: safety checks (identical to absorb_sliver_islands.py)
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
    dry_run = "--dry-run" in sys.argv

    print("=" * 70)
    print("Absorb evidence-less district parts (0 streets + 0 houses)")
    print("=" * 70)

    area_before = total_area_km2()
    boundary = boundary_area_km2()
    overlaps_before = check_overlaps()
    print(f"\nBaseline: districts total {area_before:.4f} km² | "
          f"boundary {boundary:.4f} km² | overlaps {overlaps_before}")

    # Snapshot backup early (safe even on dry-run path: it never writes geom).
    ensure_backup_column()
    if not dry_run:
        backup_geom()

    rows = find_evidenceless()
    anomalies = [r for r in rows if float(r["area_km2"]) > ABSORB_MAX_KM2]
    safe = [r for r in rows if float(r["area_km2"]) <= ABSORB_MAX_KM2]

    write_report(rows, anomalies)

    if not rows:
        print("\nNo evidence-less parts found — nothing to do.")
        return

    # Anomaly guard: refuse to apply if any candidate is a km²-scale body.
    if anomalies:
        print("\n" + "!" * 70)
        print(f"ANOMALY: {len(anomalies)} candidate part(s) exceed {ABSORB_MAX_KM2} km² "
              "— refusing to apply.")
        print("These are substantial real bodies (km²-scale) flagged as evidence-less "
              "only because their addresses failed to geocode; under the canonical "
              "street_geocodes+house_geocodes join they are NOT evidence-less. Merging "
              "them would destroy real VZN district bodies.")
        print("See report:", REPORT_PATH)
        print("!" * 70)
        sys.exit(2)

    # No-neighbour guard (a safe part must have somewhere to go).
    no_neighbor = [r for r in safe if not r.get("neighbor_id")]
    if no_neighbor:
        print(f"\nABORT: {len(no_neighbor)} part(s) have no adjacent neighbour — would "
              "create a gap. Not applying.")
        sys.exit(1)

    if dry_run:
        print(f"\n[dry-run] {len(safe)} safe part(s) would be absorbed. No write performed.")
        return

    _rebuild_geoms(safe)

    overlaps_after = check_overlaps()
    area_after = total_area_km2()
    area_drift = abs(area_after - area_before)
    print("\n[3] Safety checks:")
    print(f"  Overlap pairs: {overlaps_after} (must be 0)")
    print(f"  Total area: {area_after:.4f} km² (was {area_before:.4f}, "
          f"boundary {boundary:.4f}, drift {area_drift:.6f})")

    area_ok = area_drift < 0.001 and abs(area_after - boundary) < 0.001
    overlap_ok = overlaps_after == 0

    if not (area_ok and overlap_ok):
        print("\n!!! SAFETY CHECK FAILED — reverting !!!")
        restore_geom()
        print(f"  After restore: overlaps={check_overlaps()}, "
              f"area={total_area_km2():.4f} km²")
        sys.exit(1)

    print("\n[4] Post-absorption part counts:")
    for r in part_counts():
        parts = int(r["parts"])
        flag = f"  ⚠ MULTI-PART ({parts})" if parts > 1 else ""
        print(f"  {(r['name'] or '?')[:50]:<50} parts={parts}{flag}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Evidence-less parts absorbed: {len(safe)}")
    print(f"Overlap pairs after: {overlaps_after} (PASS)")
    print(f"Total area: {area_after:.4f} km² ≈ boundary {boundary:.4f} km² (PASS)")


if __name__ == "__main__":
    main()
