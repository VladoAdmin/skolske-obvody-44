"""
VLA-14 — Street coverage-gap classifier (engine layer, single source of truth).

Every street the streets-pivot map cannot colour (no VZN assignment) is
explicitly classified into EXACTLY one of two categories and persisted to
skolske_obvody.street_coverage_gaps, which the GUI reads via the
public.so_street_coverage_gaps view. The GUI never classifies anything.

METHODOLOGY §coverage-gaps:
  Authoritative register = register_adries_clean (habitable, not withdrawn —
  the same canonical set Step-2 address stats use). Street identity is the
  SHARED normalisation from ingest/build_street_districts.py NORM (lowercase,
  unaccent, strip Ulica-prefix/suffix + 'č.' + dots, expand 'Arm. gen.',
  collapse whitespace), so this classification can never disagree with the
  geometry build about what matched.

  vzn_gap  — street IS in the register but NO VZN row assigns it to any
             district. Addresses there have no spádový obvod: a structural
             Š1-family finding (§ 44 ods. 1 — every address belongs to exactly
             one district). Real-data evidence; may be presented as a finding.
  data_gap — the name exists only in OSM map data inside the city boundary and
             cannot be anchored to the register (spelling variants, passages,
             courtyards, transit roads, non-address spaces). We CANNOT decide,
             so it is "neurčené — dátová medzera" and MUST NEVER be presented
             as a violation (same discipline as mock-never-RED).

  Rows carry is_demo (FALSE for these real-data derivations) and engine_version.
  Idempotent: each run deletes this municipality's non-demo rows and rewrites.

Usage:
    python3 -m engine.coverage_gaps          # standalone (loads .env.local)
    (also called by engine/runner.py run())
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from engine.constants import ENGINE_VERSION, PRESOV_MUN_ID
from ingest.supabase_client import exec_sql, query_sql

# Shared street-name normalisation — MUST stay identical to
# ingest/build_street_districts.py NORM and 0040's inline copy.
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

# Evidence templates (SQL format() patterns). Intent, enforced by
# tests/test_coverage_gaps.py:
#   * vzn_gap cites § 44 / Š1 — it IS a structural finding.
#   * data_gap explicitly negates a violation — it may NEVER read as one.
REASON_VZN_GAP_SK = (
    "Ulica „%s“ je v Registri adries mesta Prešov (%s obývateľných adries), "
    "ale žiadne VZN ju nepriraďuje k školskému obvodu. Adresy na nej nemajú "
    "určený spádový obvod — štrukturálny nález Š1 (§ 44 ods. 1: každá adresa "
    "musí patriť práve jednému obvodu)."
)
REASON_DATA_GAP_SK = (
    "Neurčené — dátová medzera. Názov „%s“ existuje v mapových podkladoch "
    "(OSM), ale nedá sa priradiť k Registru adries mesta Prešov (nesúlad "
    "názvov, pasáž/priestranstvo alebo úsek bez adries), preto nemožno "
    "rozhodnúť o príslušnosti k obvodu. Nejde o zistené porušenie § 44."
)

# CTE fragments shared by both INSERTs. mun/vzn are municipality-scoped.
def _base_ctes(municipality_id: str) -> str:
    return f"""
mun AS (
  SELECT id, geom FROM skolske_obvody.municipalities
  WHERE id = '{municipality_id}'
),
vzn AS (
  SELECT DISTINCT {NORM('v.street')} AS n
  FROM skolske_obvody.vzn_street_ranges v
  JOIN skolske_obvody.districts d ON d.id = v.district_id
  WHERE d.municipality_id = (SELECT id FROM mun)
)"""


def _insert_vzn_gaps_sql(municipality_id: str) -> str:
    """Register streets (clean set) with NO VZN assignment -> vzn_gap rows."""
    return f"""
WITH {_base_ctes(municipality_id)},
reg AS (
  SELECT ulica_norm, min(ulica) AS ulica, count(*) AS addrs
  FROM skolske_obvody.register_adries_clean
  WHERE ulica_norm IS NOT NULL AND ulica_norm <> ''
  GROUP BY ulica_norm
),
gap AS (
  SELECT reg.* FROM reg
  WHERE NOT EXISTS (SELECT 1 FROM vzn WHERE vzn.n = reg.ulica_norm)
),
-- OSM centerlines for the gap street (union of all same-named ways, clipped)
lines AS (
  SELECT {NORM('o.name')} AS n,
         public.ST_Multi(public.ST_Union(
           public.ST_Intersection(o.geom, (SELECT geom FROM mun)))) AS geom
  FROM skolske_obvody.osm_street_lines o
  WHERE public.ST_Intersects(o.geom, (SELECT geom FROM mun))
    AND {NORM('o.name')} IN (SELECT ulica_norm FROM gap)
  GROUP BY {NORM('o.name')}
)
INSERT INTO skolske_obvody.street_coverage_gaps
  (municipality_id, street, street_norm, category, in_register, in_vzn,
   register_address_count, has_osm_line, reason_sk, provenance, geom,
   is_demo, engine_version)
SELECT
  (SELECT id FROM mun),
  g.ulica,
  g.ulica_norm,
  'vzn_gap',
  TRUE,
  FALSE,
  g.addrs,
  l.geom IS NOT NULL,
  format($fmt${REASON_VZN_GAP_SK}$fmt$, g.ulica, g.addrs),
  jsonb_build_object(
    'sources', jsonb_build_array(
      'register_adries_clean', 'vzn_street_ranges', 'osm_street_lines'),
    'register_address_count', g.addrs,
    'vzn_match', false,
    'osm_line', l.geom IS NOT NULL,
    'method', 'normalised street-name join (build_street_districts NORM)'
  ),
  l.geom,
  FALSE,
  '{ENGINE_VERSION}'
FROM gap g
LEFT JOIN lines l ON l.n = g.ulica_norm
"""


def _insert_data_gaps_sql(municipality_id: str) -> str:
    """OSM names inside the city matched to NEITHER VZN NOR register -> data_gap."""
    return f"""
WITH {_base_ctes(municipality_id)},
regn AS (
  SELECT DISTINCT ulica_norm FROM skolske_obvody.register_adries_clean
  WHERE ulica_norm IS NOT NULL AND ulica_norm <> ''
),
osm AS (
  SELECT {NORM('o.name')} AS n,
         min(o.name) AS name,
         public.ST_Multi(public.ST_Union(
           public.ST_Intersection(o.geom, (SELECT geom FROM mun)))) AS geom
  FROM skolske_obvody.osm_street_lines o
  WHERE o.name IS NOT NULL
    AND public.ST_Intersects(o.geom, (SELECT geom FROM mun))
  GROUP BY {NORM('o.name')}
),
gap AS (
  SELECT * FROM osm
  WHERE n <> ''
    AND NOT EXISTS (SELECT 1 FROM vzn  WHERE vzn.n = osm.n)
    AND NOT EXISTS (SELECT 1 FROM regn WHERE regn.ulica_norm = osm.n)
)
INSERT INTO skolske_obvody.street_coverage_gaps
  (municipality_id, street, street_norm, category, in_register, in_vzn,
   register_address_count, has_osm_line, reason_sk, provenance, geom,
   is_demo, engine_version)
SELECT
  (SELECT id FROM mun),
  g.name,
  g.n,
  'data_gap',
  FALSE,
  FALSE,
  0,
  TRUE,
  format($fmt${REASON_DATA_GAP_SK}$fmt$, g.name),
  jsonb_build_object(
    'sources', jsonb_build_array(
      'osm_street_lines', 'register_adries_clean', 'vzn_street_ranges'),
    'register_match', false,
    'vzn_match', false,
    'method', 'normalised street-name join (build_street_districts NORM)'
  ),
  g.geom,
  FALSE,
  '{ENGINE_VERSION}'
FROM gap g
"""


def classify_coverage_gaps(municipality_id: str = PRESOV_MUN_ID) -> dict:
    """
    Full refresh of street_coverage_gaps for one municipality. Returns
    {'vzn_gap': n, 'data_gap': n}. Demo rows (is_demo) are never touched.
    """
    res = exec_sql(
        f"DELETE FROM skolske_obvody.street_coverage_gaps "
        f"WHERE municipality_id = '{municipality_id}' AND is_demo = FALSE"
    )
    if not res.get("ok"):
        raise RuntimeError(f"coverage-gap cleanup failed: {res.get('message')}")

    for label, sql in (
        ("vzn_gap", _insert_vzn_gaps_sql(municipality_id)),
        ("data_gap", _insert_data_gaps_sql(municipality_id)),
    ):
        res = exec_sql(sql)
        if not res.get("ok"):
            raise RuntimeError(f"coverage-gap insert ({label}) failed: {res.get('message')}")

    rows = query_sql(
        f"SELECT category, count(*) AS n, "
        f"count(*) FILTER (WHERE geom IS NOT NULL) AS with_geom, "
        f"sum(register_address_count) AS addrs "
        f"FROM skolske_obvody.street_coverage_gaps "
        f"WHERE municipality_id = '{municipality_id}' AND is_demo = FALSE "
        f"GROUP BY category ORDER BY category"
    )
    stats = {"vzn_gap": 0, "data_gap": 0}
    for r in rows:
        stats[r["category"]] = int(r["n"])
        print(f"  coverage {r['category']}: {r['n']} streets "
              f"({r['with_geom']} with geometry, {r['addrs'] or 0} register addresses)")
    return stats


if __name__ == "__main__":
    # Load .env.local if present (same pattern as engine/runner.py)
    import os
    env_path = ".env.local"
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    from ingest.config import validate_config
    validate_config()
    print(f"Coverage-gap classification (engine v{ENGINE_VERSION})")
    stats = classify_coverage_gaps()
    print(f"Done: vzn_gap={stats['vzn_gap']} data_gap={stats['data_gap']}")
