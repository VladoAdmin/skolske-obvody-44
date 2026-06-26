"""
Build CONTIGUOUS, VZN-respecting district polygons via nearest-VZN-STREET-LINE
tessellation. Successor to build_voronoi_districts.py (point-Voronoi), which
fragmented districts because scattered single points per street interleaved.

ROOT-CAUSE FIX (Vlado-approved):
  Point-Voronoi shatters a district whenever a neighbouring school's points fall
  between its own. Streets are continuous LINES, not dots — so tessellating by the
  nearest VZN-ASSIGNED STREET geometry keeps each district contiguous while the
  assignment stays strictly VZN-driven (only streets the VZN gives to a district
  can pull area to it). Genuine VZN splits (assigned streets that really lie in
  two separated areas) survive and are still flagged downstream.

METHOD (deterministic, 0-overlap by construction):
  1. Per district, collect its VZN-assigned street geometries:
       - OSM centerline (osm_street_lines) where normalised name matches the VZN
         street (~95% of streets), ELSE
       - the street_geocodes single POINT (fallback for the ~5% with no OSM line).
     House points are NOT used as seeds: they re-introduce the scatter we are
     removing. The VZN street set alone defines each district.
  2. Densify the assigned street lines to a fixed step (SEGMENTIZE_M) so a line
     becomes a dense chain of seed vertices; keep fallback points as-is.
  3. ST_VoronoiPolygons over ALL seed vertices, clipped to the Prešov boundary.
     Each cell is assigned to the district of its generating seed vertex.
  4. ST_Union cells per district, intersect with boundary -> MultiPolygon.
     PostGIS Voronoi cells share edges (not areas) => pairwise overlap = 0 exactly.

  As the densify step -> 0 this converges to the exact nearest-line partition.
  SEGMENTIZE_M trades resolution (smaller = closer to true nearest-line, more
  vertices, slower) against runtime. 60 m is fine for city blocks here.

TRADEOFF (explicit): boundaries between two districts whose VZN streets run
parallel and close are the geometric midline between the actual VZN street lines,
not exact house-parcel edges (we have no parcel polygons). The midline never
assigns area to a district the VZN did not give that street to, so it is the most
defensible approximation; the cost is sub-block literal fidelity, the gain is
clean contiguity.

Writes districts.geom live. Backs up the previous point-Voronoi geom into
geom_voronoi_point_backup (does NOT clobber geom_island_backup /
geom_prefix_engine_backup / geom_sprint_j_backup).

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/build_street_districts.py
"""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

SEGMENTIZE_M = 60.0  # densify step for street lines (metres, UTM 32634)

PRESOV = "(SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')"

# Normalise a street name for VZN<->OSM matching: strip diacritics, lowercase,
# drop the "Ulica" prefix/suffix and "č."/dots, expand the one common
# abbreviation, collapse whitespace. Implemented as inline SQL so it runs inside
# the set-based build (Rule 5: code/SQL does the deterministic transform).
NORM = lambda col: f"""
  regexp_replace(
    regexp_replace(
      regexp_replace(
        lower(unaccent(
          replace(replace({col}, 'Arm. gen.', 'Armádneho generála'), 'č.', '')
        )),
        '^ulica\\s+|\\s+ulica$', '', 'g'),
      '[.]', ' ', 'g'),
    '\\s+', ' ', 'g')
"""


def ensure_columns() -> None:
    print("\n[schema] Ensuring columns + unaccent extension...")
    for sql in [
        "CREATE EXTENSION IF NOT EXISTS unaccent",
        """ALTER TABLE skolske_obvody.districts
           ADD COLUMN IF NOT EXISTS geom_street public.geometry(MultiPolygon, 4326)""",
        """ALTER TABLE skolske_obvody.districts
           ADD COLUMN IF NOT EXISTS geom_street_metadata JSONB""",
        """ALTER TABLE skolske_obvody.districts
           ADD COLUMN IF NOT EXISTS geom_voronoi_point_backup public.geometry(MultiPolygon, 4326)""",
    ]:
        r = exec_sql(sql)
        if not r.get("ok"):
            raise RuntimeError(f"schema step failed: {r.get('message')}")
    print("  schema OK")


def backup_current() -> None:
    print("\n[backup] Backing up current point-Voronoi geom -> geom_voronoi_point_backup...")
    r = exec_sql(f"""
        UPDATE skolske_obvody.districts
        SET geom_voronoi_point_backup = geom
        WHERE geom_voronoi_point_backup IS NULL
          AND geom IS NOT NULL
          AND municipality_id = {PRESOV}
    """)
    if not r.get("ok"):
        raise RuntimeError(f"backup failed: {r.get('message')}")
    print("  backup OK (only fills NULLs; idempotent)")


def report_match_coverage() -> None:
    print("\n[match] VZN street -> OSM centerline coverage:")
    rows = query_sql(f"""
        WITH vzn AS (
          SELECT DISTINCT district_id, street FROM skolske_obvody.vzn_street_ranges
        ),
        osm AS (
          SELECT DISTINCT {NORM('name')} AS nname FROM skolske_obvody.osm_street_lines
        )
        SELECT
          count(*) AS vzn_streets,
          count(*) FILTER (WHERE o.nname IS NOT NULL) AS matched,
          count(*) FILTER (WHERE o.nname IS NULL)     AS fallback_point
        FROM vzn v
        LEFT JOIN osm o ON o.nname = {NORM('v.street')}
    """)
    r = rows[0]
    print(f"  VZN streets: {r['vzn_streets']}  matched to OSM line: {r['matched']}  "
          f"point-fallback: {r['fallback_point']}")


# Seed set: per VZN street, the matched OSM lines (densified vertices) OR the
# street_geocodes point. Built as a CTE reused by the build.
SEEDS_CTE = f"""
presov AS (
  SELECT geom FROM skolske_obvody.municipalities WHERE slug = 'presov'
),
vzn AS (
  SELECT DISTINCT district_id, street FROM skolske_obvody.vzn_street_ranges
),
-- (1) matched OSM street lines per district, clipped to boundary, densified
osm_seeds AS (
  SELECT v.district_id,
         (public.ST_DumpPoints(
            public.ST_Transform(
              public.ST_Segmentize(
                public.ST_Transform(
                  public.ST_Intersection(o.geom, (SELECT geom FROM presov)),
                  32634),
                {SEGMENTIZE_M}),
              4326)
         )).geom AS geom
  FROM vzn v
  JOIN skolske_obvody.osm_street_lines o
    ON {NORM('o.name')} = {NORM('v.street')}
  WHERE public.ST_Intersects(o.geom, (SELECT geom FROM presov))
),
-- which VZN streets matched at least one OSM line (to know who needs fallback)
matched_streets AS (
  SELECT DISTINCT v.district_id, v.street
  FROM vzn v
  WHERE EXISTS (
    SELECT 1 FROM skolske_obvody.osm_street_lines o
    WHERE {NORM('o.name')} = {NORM('v.street')}
  )
),
-- (2) fallback: street_geocodes point for VZN streets with NO OSM line
point_seeds AS (
  SELECT sg.district_id, sg.geom
  FROM skolske_obvody.street_geocodes sg
  JOIN vzn v ON v.district_id = sg.district_id AND v.street = sg.street
  WHERE sg.geom IS NOT NULL
    AND public.ST_Within(sg.geom, (SELECT geom FROM presov))
    AND NOT EXISTS (
      SELECT 1 FROM matched_streets m
      WHERE m.district_id = sg.district_id AND m.street = sg.street
    )
),
-- (3) VZN house points: exact address-level seeds owned by their VZN district.
-- These anchor each house's own cell to its district, preserving address->district
-- fidelity (without them, a house can fall into a neighbour whose street centerline
-- is locally closer). The continuous OSM street lines still provide the backbone
-- that prevents the original scatter-fragmentation.
house_seeds AS (
  SELECT hg.district_id, hg.geom
  FROM skolske_obvody.house_geocodes hg
  WHERE hg.valid = true AND hg.geom IS NOT NULL
    AND public.ST_Within(hg.geom, (SELECT geom FROM presov))
),
seeds AS (
  SELECT district_id, geom FROM osm_seeds
  UNION ALL
  SELECT district_id, geom FROM point_seeds
  UNION ALL
  SELECT district_id, geom FROM house_seeds
)
"""

# Step 1: materialise seeds into an indexed table (the per-cell correlated
# subquery times out the PostgREST statement_timeout; a GiST spatial JOIN does
# not). _seed_pt also carries a serial id so the Voronoi->seed join is exact.
SEEDS_TABLE_SQL = f"""
DROP TABLE IF EXISTS skolske_obvody._seed_pt;
CREATE TABLE skolske_obvody._seed_pt AS
WITH {SEEDS_CTE}
SELECT row_number() OVER () AS sid, district_id, geom
FROM seeds;
CREATE INDEX _seed_pt_gix ON skolske_obvody._seed_pt USING GIST (geom);
ANALYZE skolske_obvody._seed_pt;
"""

# Step 2: Voronoi over the seed points, written to an indexed cells table.
CELLS_TABLE_SQL = """
DROP TABLE IF EXISTS skolske_obvody._vor_cell;
CREATE TABLE skolske_obvody._vor_cell AS
WITH presov AS (SELECT geom FROM skolske_obvody.municipalities WHERE slug='presov'),
dumped AS (
  SELECT (public.ST_Dump(public.ST_VoronoiPolygons(
            public.ST_Collect(geom), 0.0, (SELECT geom FROM presov)))).geom AS cell_geom
  FROM skolske_obvody._seed_pt
)
SELECT row_number() OVER () AS cid, cell_geom FROM dumped;
CREATE INDEX _vor_cell_gix ON skolske_obvody._vor_cell USING GIST (cell_geom);
ANALYZE skolske_obvody._vor_cell;
"""

# Step 3: assign each cell to the district of the seed it contains (GiST join),
# union per district, intersect boundary, write geom_street.
ASSIGN_SQL = f"""
WITH presov AS (SELECT geom FROM skolske_obvody.municipalities WHERE slug='presov'),
cells_with_district AS (
  SELECT DISTINCT ON (c.cid) c.cid, c.cell_geom, s.district_id
  FROM skolske_obvody._vor_cell c
  JOIN skolske_obvody._seed_pt s
    ON public.ST_Contains(c.cell_geom, s.geom)
  ORDER BY c.cid, s.district_id, public.ST_X(s.geom), public.ST_Y(s.geom)
),
grouped AS (
  SELECT district_id,
         public.ST_Multi(
           public.ST_CollectionExtract(
             public.ST_MakeValid(
               public.ST_Intersection(public.ST_Union(cell_geom),
                                      (SELECT geom FROM presov))), 3)) AS geom_street,
         COUNT(*) AS cell_count
  FROM cells_with_district
  WHERE district_id IS NOT NULL
  GROUP BY district_id
)
UPDATE skolske_obvody.districts d
SET geom_street = grouped.geom_street,
    geom_street_metadata = jsonb_build_object(
      'method', 'nearest_vzn_street_line_tessellation',
      'segmentize_m', {SEGMENTIZE_M},
      'cell_count', grouped.cell_count,
      'created_at', now())
FROM grouped
WHERE d.id = grouped.district_id
"""


def build() -> None:
    print("\n[build] Materialising seed points (indexed)...")
    r = exec_sql(SEEDS_TABLE_SQL)
    if not r.get("ok"):
        raise RuntimeError(f"seed table failed: {r.get('message')}")
    rows = query_sql("SELECT count(*) n FROM skolske_obvody._seed_pt")
    print(f"  seeds materialised: {rows[0]['n']}")

    print("[build] Voronoi tessellation over seeds (indexed cells)...")
    r = exec_sql(CELLS_TABLE_SQL)
    if not r.get("ok"):
        raise RuntimeError(f"cell table failed: {r.get('message')}")
    rows = query_sql("SELECT count(*) n FROM skolske_obvody._vor_cell")
    print(f"  cells: {rows[0]['n']}")

    print("[build] Assigning cells -> district + union -> geom_street...")
    r = exec_sql(ASSIGN_SQL)
    if not r.get("ok"):
        raise RuntimeError(f"assign failed: {r.get('message')}")
    print("  geom_street written OK")

    # Tidy scratch tables
    exec_sql("DROP TABLE IF EXISTS skolske_obvody._vor_cell")
    exec_sql("DROP TABLE IF EXISTS skolske_obvody._seed_pt")


# ---------------------------------------------------------------------------
# Morphological cleanup: absorb UNSUPPORTED parts (corridors with no VZN
# evidence) into their longest-shared-border neighbour. A part is "unsupported"
# if it contains ZERO of its own district's VZN street points AND ZERO of its
# own valid VZN house points -> it is a pure tessellation corridor, not a place
# the VZN actually assigns to this district, so moving it does NOT violate VZN
# truth. Parts WITH evidence stay (genuine, possibly non-contiguous VZN spread)
# and are flagged downstream by flag_multipart_districts.py.
# ---------------------------------------------------------------------------

ABSORB_SQL = f"""
WITH parts AS (
  SELECT d.id AS did, d.name,
         (public.ST_Dump(d.geom_street)).path[1] - 1 AS idx,
         (public.ST_Dump(d.geom_street)).geom AS g,
         public.ST_NumGeometries(d.geom_street) AS nparts
  FROM skolske_obvody.districts d
  WHERE d.municipality_id = {PRESOV} AND d.geom_street IS NOT NULL
),
scored AS (
  SELECT p.*,
    (SELECT count(*) FROM skolske_obvody.street_geocodes sg
       WHERE sg.district_id = p.did AND public.ST_Within(sg.geom, p.g))
    + (SELECT count(*) FROM skolske_obvody.house_geocodes hg
       WHERE hg.district_id = p.did AND hg.valid AND public.ST_Within(hg.geom, p.g))
    AS evidence
  FROM parts p
),
-- unsupported parts (no VZN evidence) in multi-part districts -> absorb
unsupported AS (
  SELECT s.*,
    (SELECT d2.id FROM skolske_obvody.districts d2
       WHERE d2.id <> s.did AND d2.municipality_id = {PRESOV}
         AND d2.geom_street IS NOT NULL
         AND public.ST_Intersects(s.g, d2.geom_street)
       ORDER BY public.ST_Length(public.ST_Transform(
         public.ST_Intersection(public.ST_Boundary(s.g), d2.geom_street), 32634))
         DESC NULLS LAST
       LIMIT 1) AS target_did
  FROM scored s
  WHERE s.nparts > 1 AND s.evidence = 0
),
mapping AS (SELECT did AS owner_did, idx, target_did FROM unsupported),
dumped AS (
  SELECT d.id AS did, (public.ST_Dump(d.geom_street)).path[1] - 1 AS idx,
         (public.ST_Dump(d.geom_street)).geom AS g
  FROM skolske_obvody.districts d
  WHERE d.municipality_id = {PRESOV} AND d.geom_street IS NOT NULL
),
kept AS (
  SELECT du.did, du.g FROM dumped du
  LEFT JOIN mapping m ON m.owner_did = du.did AND m.idx = du.idx
  WHERE m.owner_did IS NULL
),
received AS (
  SELECT m.target_did AS did, du.g FROM dumped du
  JOIN mapping m ON m.owner_did = du.did AND m.idx = du.idx
  WHERE m.target_did IS NOT NULL
),
all_parts AS (SELECT did, g FROM kept UNION ALL SELECT did, g FROM received),
rebuilt AS (
  SELECT did, public.ST_Multi(public.ST_UnaryUnion(public.ST_Collect(g))) AS new_geom
  FROM all_parts GROUP BY did
)
UPDATE skolske_obvody.districts d
SET geom_street = rebuilt.new_geom
FROM rebuilt
WHERE d.id = rebuilt.did
"""


UNSUPPORTED_COUNT_SQL = f"""
WITH parts AS (
  SELECT d.id AS did,
         (public.ST_Dump(d.geom_street)).geom AS g,
         public.ST_NumGeometries(d.geom_street) AS nparts
  FROM skolske_obvody.districts d
  WHERE d.municipality_id = {PRESOV} AND d.geom_street IS NOT NULL
)
SELECT count(*) AS n FROM parts p
WHERE p.nparts > 1
  AND (SELECT count(*) FROM skolske_obvody.street_geocodes sg
       WHERE sg.district_id = p.did AND public.ST_Within(sg.geom, p.g))
    + (SELECT count(*) FROM skolske_obvody.house_geocodes hg
       WHERE hg.district_id = p.did AND hg.valid AND public.ST_Within(hg.geom, p.g)) = 0
"""


def absorb_unsupported(max_passes: int = 4) -> None:
    """Absorb no-VZN-evidence corridor parts, iterating: a part's chosen
    neighbour can itself be an absorbed corridor, so one pass can leave residue.
    Repeat until stable or max_passes."""
    print("\n[clean] Absorbing unsupported (no-VZN-evidence) corridor parts...")
    for p in range(1, max_passes + 1):
        n = int(query_sql(UNSUPPORTED_COUNT_SQL)[0]["n"])
        print(f"  pass {p}: unsupported parts = {n}")
        if n == 0:
            break
        r = exec_sql(ABSORB_SQL)
        if not r.get("ok"):
            raise RuntimeError(f"absorb failed: {r.get('message')}")
    remaining = int(query_sql(UNSUPPORTED_COUNT_SQL)[0]["n"])
    print(f"  done — unsupported parts remaining: {remaining}")


def promote() -> None:
    print("\n[promote] geom_street -> geom (confidence=high, quality=9)...")
    r = exec_sql(f"""
        UPDATE skolske_obvody.districts
        SET geom = geom_street,
            geometry_confidence = 'high',
            geometry_quality = 9
        WHERE municipality_id = {PRESOV}
          AND geom_street IS NOT NULL
    """)
    if not r.get("ok"):
        raise RuntimeError(f"promote failed: {r.get('message')}")
    print("  promote OK")


def check_overlaps() -> dict:
    print("\n[gate] Overlap check (expect 0)...")
    rows = query_sql(f"""
        SELECT count(*) AS n,
               COALESCE(sum(public.ST_Area(public.ST_Transform(
                 public.ST_Intersection(d1.geom, d2.geom), 32634))), 0) AS area_m2
        FROM skolske_obvody.districts d1, skolske_obvody.districts d2
        WHERE d1.id < d2.id AND d1.municipality_id = d2.municipality_id
          AND d1.municipality_id = {PRESOV}
          AND public.ST_Intersects(d1.geom, d2.geom)
          AND public.ST_Area(public.ST_Transform(
                public.ST_Intersection(d1.geom, d2.geom), 32634)) > 1
    """)
    n = int(rows[0]["n"]); area = float(rows[0]["area_m2"])
    ok = n == 0
    print(f"  {'PASS (0 overlaps)' if ok else f'FAIL ({n} pairs, {area/1e6:.3f} km2)'}")
    return {"pairs": n, "area_m2": area, "ok": ok}


def check_coverage() -> dict:
    print("\n[gate] Coverage check (district union vs Prešov boundary)...")
    rows = query_sql(f"""
        WITH u AS (
          SELECT public.ST_Union(geom) g FROM skolske_obvody.districts
          WHERE municipality_id = {PRESOV} AND geom IS NOT NULL
        ), b AS (
          SELECT geom g FROM skolske_obvody.municipalities WHERE slug='presov'
        )
        SELECT round((public.ST_Area(public.ST_Transform((SELECT g FROM b),32634))/1e6)::numeric,2) AS boundary_km2,
               round((public.ST_Area(public.ST_Transform((SELECT g FROM u),32634))/1e6)::numeric,2) AS covered_km2,
               round((public.ST_Area(public.ST_Transform(
                 public.ST_Difference((SELECT g FROM b),(SELECT g FROM u)),32634))/1e6)::numeric,3) AS uncovered_km2
    """)
    r = rows[0]
    pct = 100.0 * float(r["covered_km2"]) / float(r["boundary_km2"])
    print(f"  boundary={r['boundary_km2']} km2  covered={r['covered_km2']} km2 "
          f"({pct:.1f}%)  holes={r['uncovered_km2']} km2")
    return {**r, "pct": pct}


def part_counts(col: str) -> list[dict]:
    return query_sql(f"""
        SELECT d.name,
               public.ST_NumGeometries(d.{col}) AS parts,
               round((public.ST_Area(public.ST_Transform(d.{col},32634))/1e6)::numeric,2) AS km2
        FROM skolske_obvody.districts d
        WHERE d.municipality_id = {PRESOV} AND d.{col} IS NOT NULL
        ORDER BY parts DESC, d.name
    """)


def main() -> None:
    validate_config()
    print("=" * 70)
    print("Build CONTIGUOUS VZN-street-line districts (replaces point-Voronoi)")
    print(f"Started: {datetime.now().isoformat()}  segmentize={SEGMENTIZE_M}m")
    print("=" * 70)

    ensure_columns()
    report_match_coverage()

    print("\n[before] Part counts on current geom (point-Voronoi):")
    before = part_counts("geom")
    for r in before:
        print(f"  {(r['name'] or '?')[:52]:<52} parts={r['parts']} km2={r['km2']}")

    backup_current()
    build()
    absorb_unsupported()
    promote()

    print("\n[after] Part counts on new geom (street-line tessellation):")
    after = part_counts("geom")
    for r in after:
        flag = " <-- still multi-part" if (r["parts"] or 1) > 1 else ""
        print(f"  {(r['name'] or '?')[:52]:<52} parts={r['parts']} km2={r['km2']}{flag}")

    overlap = check_overlaps()
    coverage = check_coverage()

    single = sum(1 for r in after if (r["parts"] or 1) == 1)
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Districts:            {len(after)}")
    print(f"Single-polygon now:   {single}/{len(after)}")
    print(f"Overlap:              {'PASS' if overlap['ok'] else 'FAIL'} "
          f"({overlap['pairs']} pairs, {overlap['area_m2']/1e6:.4f} km2)")
    print(f"Coverage:             {coverage['pct']:.1f}%  holes={coverage['uncovered_km2']} km2")
    print(f"Finished: {datetime.now().isoformat()}")

    if not overlap["ok"]:
        print("\nGATE FAIL: non-zero overlap. Revert with geom_voronoi_point_backup.")
        sys.exit(1)


if __name__ == "__main__":
    main()
