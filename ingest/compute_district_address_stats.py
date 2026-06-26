"""
Per-district authoritative address statistics (zero API cost).

Originally (Sprint register-geocode-confidence) this computed counts against the
RAW register (register_adries, habitable rows). Step 4 (display-rederived-data)
adds the CLEANED authoritative numbers + a geometric-consistency signal, computed
against the Step-2 cleaned canonical set and the Step-3 geometric validation, and
persists them so the UI shows the authoritative figures.

Per district (all from VZN street->district map + the register, no API calls):
  RAW (kept for back-compat, the original confidence line):
  - habitable_addresses     : raw habitable register addresses on VZN streets
  - register_streets        : distinct raw register streets matched
  - vzn_streets             : distinct VZN streets assigned to this district
  - vzn_streets_in_register : how many VZN streets exist in the raw register
  - street_coverage         : vzn_streets_in_register / vzn_streets (0..1)

  CLEAN (authoritative — what the scorecard now shows, Step 2 data):
  - clean_habitable_addresses : habitable addresses from register_adries_clean
  - clean_distinct_streets    : distinct cleaned streets matched to this district
  - clean_street_coverage     : share of this district's VZN streets with >=1
                                cleaned register address (0..1)

  GEOMETRIC CONSISTENCY (Step 3 signal — a place to review, NOT a verdict):
  - mismatch_count            : geocoded addresses the VZN assigns to THIS
                                district whose real coordinate falls OUTSIDE this
                                district's polygon. Also persisted per address in
                                skolske_obvody.register_mismatches for the expert
                                map layer.

Street name matching uses the same normalisation as build_street_districts.py
(strip diacritics/Ulica/dots, expand the one abbreviation) + a trailing-trim.

A street the VZN assigns to >1 district is attributed to EACH such district (the
address-level split is exactly what geocoding resolves; for the count signal both
districts legitimately list the street). A range-split address whose coordinate
lands in neither VZN district therefore counts as a mismatch for each VZN
district it was assigned to — i.e. the figure flags "addresses this district was
told to own but whose real point is elsewhere".

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/compute_district_address_stats.py
"""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

PRESOV = "(SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')"

# Same normalisation family as build_street_districts.py, with an outer btrim so
# trailing-dot register variants ("Veterná.") match the VZN street ("Veterná").
NORM = lambda col: f"""
  btrim(regexp_replace(
    regexp_replace(
      regexp_replace(
        lower(unaccent(
          replace(replace({col}, 'Arm. gen.', 'Armádneho generála'), 'č.', '')
        )),
        '^ulica\\s+|\\s+ulica$', '', 'g'),
      '[.]', ' ', 'g'),
    '\\s+', ' ', 'g'))
"""


SCHEMA_FILES = (
    "scripts/sql/0023_register_geocode_and_stats.sql",
    "scripts/sql/0027_district_stats_clean_and_mismatch.sql",
)


def apply_schema() -> None:
    for path in SCHEMA_FILES:
        print(f"\n[schema] Applying {path} ...")
        with open(path, encoding="utf-8") as fh:
            sql = fh.read()
        r = exec_sql(sql)
        if not r.get("ok"):
            raise RuntimeError(f"schema apply failed ({path}): {r.get('message')}")
        print("  schema OK")


def compute() -> None:
    print("\n[compute] Per-district authoritative address stats (no API calls)...")
    # vzn: distinct (district, normalised street) the VZN assigns.
    # reg: habitable RAW register rows (back-compat confidence line).
    # clean: habitable deduped rows from register_adries_clean (Step-2 set,
    #        the authoritative numbers the scorecard now shows).
    # Per (district, vzn street) we LEFT JOIN register rows on the normalised
    # name; counting rows gives habitable_addresses, and counting district VZN
    # streets that have >=1 row gives coverage. The RAW and CLEAN columns use
    # the same shape against their respective source tables.
    sql = f"""
WITH vzn AS (
  SELECT DISTINCT vr.district_id, {NORM('vr.street')} AS nname
  FROM skolske_obvody.vzn_street_ranges vr
  JOIN skolske_obvody.districts d ON d.id = vr.district_id
  WHERE d.municipality_id = {PRESOV}
),
reg AS (
  SELECT {NORM('ra.ulica')} AS nname, ra.id, ra.ulica
  FROM skolske_obvody.register_adries ra
  WHERE ra.obyvatelna = true
),
clean AS (
  SELECT c.ulica_norm AS nname, c.id, c.ulica
  FROM skolske_obvody.register_adries_clean c
),
joined AS (
  SELECT v.district_id, v.nname AS vzn_nname,
         r.id  AS reg_id,   r.ulica AS reg_ulica,
         cl.id AS clean_id, cl.nname AS clean_nname
  FROM vzn v
  LEFT JOIN reg r ON r.nname = v.nname
  LEFT JOIN clean cl ON cl.nname = v.nname
),
agg AS (
  SELECT
    district_id,
    count(DISTINCT reg_id)                             AS habitable_addresses,
    count(DISTINCT reg_ulica)                          AS register_streets,
    count(DISTINCT vzn_nname)                          AS vzn_streets,
    count(DISTINCT vzn_nname) FILTER (WHERE reg_id IS NOT NULL) AS vzn_streets_in_register,
    count(DISTINCT clean_id)                           AS clean_habitable_addresses,
    count(DISTINCT clean_nname)                        AS clean_distinct_streets,
    count(DISTINCT vzn_nname) FILTER (WHERE clean_id IS NOT NULL) AS vzn_streets_in_clean
  FROM joined
  GROUP BY district_id
),
mism AS (
  SELECT vzn_district_id AS district_id, count(*) AS mismatch_count
  FROM skolske_obvody.register_mismatches
  GROUP BY vzn_district_id
)
INSERT INTO skolske_obvody.district_address_stats
  (district_id, habitable_addresses, register_streets, vzn_streets,
   vzn_streets_in_register, street_coverage,
   clean_habitable_addresses, clean_distinct_streets, clean_street_coverage,
   mismatch_count, computed_at)
SELECT
  a.district_id,
  a.habitable_addresses,
  a.register_streets,
  a.vzn_streets,
  a.vzn_streets_in_register,
  CASE WHEN a.vzn_streets > 0
       THEN round((a.vzn_streets_in_register::numeric / a.vzn_streets), 4)
       ELSE 0 END,
  a.clean_habitable_addresses,
  a.clean_distinct_streets,
  CASE WHEN a.vzn_streets > 0
       THEN round((a.vzn_streets_in_clean::numeric / a.vzn_streets), 4)
       ELSE 0 END,
  COALESCE(m.mismatch_count, 0),
  now()
FROM agg a
LEFT JOIN mism m ON m.district_id = a.district_id
ON CONFLICT (district_id) DO UPDATE SET
  habitable_addresses       = EXCLUDED.habitable_addresses,
  register_streets          = EXCLUDED.register_streets,
  vzn_streets               = EXCLUDED.vzn_streets,
  vzn_streets_in_register   = EXCLUDED.vzn_streets_in_register,
  street_coverage           = EXCLUDED.street_coverage,
  clean_habitable_addresses = EXCLUDED.clean_habitable_addresses,
  clean_distinct_streets    = EXCLUDED.clean_distinct_streets,
  clean_street_coverage     = EXCLUDED.clean_street_coverage,
  mismatch_count            = EXCLUDED.mismatch_count,
  computed_at               = EXCLUDED.computed_at
"""
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"compute failed: {r.get('message')}")
    print("  stats written OK")


def populate_mismatches() -> None:
    """Persist the Step-3 geometric mismatches per (address, VZN district).

    One row per geocoded address the VZN assigns to a district whose REAL
    coordinate falls in a different district's polygon (or no polygon). A street
    the VZN splits across districts is attributed to each such district, so a
    range-split point whose coordinate lands in neither legitimately surfaces
    once per VZN district it was assigned to. This is a data-quality signal, not
    a verdict change. Mirrors rederive_districts_analysis.geometric_validation.
    """
    print("\n[mismatch] Persisting per-address geometric mismatches...")
    sql = f"""
WITH vzn AS (
  SELECT DISTINCT vr.district_id, {NORM('vr.street')} AS nname
  FROM skolske_obvody.vzn_street_ranges vr
  JOIN skolske_obvody.districts d ON d.id = vr.district_id
  WHERE d.municipality_id = {PRESOV}
),
pts AS (
  SELECT g.adresa, g.ulica, g.lat, g.lon, g.geom, {NORM('g.ulica')} AS nname
  FROM skolske_obvody.register_geocode g
  WHERE g.geom IS NOT NULL
),
in_poly AS (
  SELECT p.adresa, p.ulica, p.nname, p.lat, p.lon, p.geom,
    (SELECT d.id FROM skolske_obvody.districts d
       WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
         AND public.ST_Covers(d.geom, p.geom)
       LIMIT 1) AS poly_did
  FROM pts p
),
-- the set of VZN districts for the point's street, so a point is a MATCH if its
-- covering polygon is ANY of the street's VZN districts.
vzn_set AS (
  SELECT ip.adresa, array_agg(DISTINCT v.district_id) AS vzn_dids
  FROM in_poly ip JOIN vzn v ON v.nname = ip.nname
  GROUP BY ip.adresa
),
-- one mismatch row per (address, each VZN district it was assigned to) when the
-- covering polygon is none of the street's VZN districts.
mismatch AS (
  SELECT ip.adresa, ip.ulica, v.district_id AS vzn_district_id,
         ip.poly_did AS poly_district_id, ip.lat, ip.lon, ip.geom
  FROM in_poly ip
  JOIN vzn_set vs ON vs.adresa = ip.adresa
  JOIN vzn v ON v.nname = ip.nname
  WHERE ip.poly_did IS NULL OR NOT (ip.poly_did = ANY (vs.vzn_dids))
)
INSERT INTO skolske_obvody.register_mismatches
  (adresa, ulica, vzn_district_id, poly_district_id, lat, lon, geom, computed_at)
SELECT adresa, ulica, vzn_district_id, poly_district_id, lat, lon, geom, now()
FROM mismatch
ON CONFLICT (adresa, vzn_district_id) DO UPDATE SET
  ulica            = EXCLUDED.ulica,
  poly_district_id = EXCLUDED.poly_district_id,
  lat              = EXCLUDED.lat,
  lon              = EXCLUDED.lon,
  geom             = EXCLUDED.geom,
  computed_at      = EXCLUDED.computed_at
"""
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"mismatch populate failed: {r.get('message')}")
    print("  mismatches written OK")


def report() -> int:
    rows = query_sql(f"""
        SELECT d.name,
               s.clean_habitable_addresses, s.clean_distinct_streets,
               s.clean_street_coverage, s.mismatch_count
        FROM skolske_obvody.district_address_stats s
        JOIN skolske_obvody.districts d ON d.id = s.district_id
        WHERE d.municipality_id = {PRESOV}
        ORDER BY s.clean_habitable_addresses DESC
    """)
    print("\n" + "=" * 72)
    print("PER-DISTRICT AUTHORITATIVE (CLEAN) ADDRESS STATS")
    print("=" * 72)
    print(f"{'District':<46}{'cAddr':>6}{'cStr':>5}{'cCov':>7}{'mism':>6}")
    for r in rows:
        print(f"{(r['name'] or '?')[:45]:<46}"
              f"{r['clean_habitable_addresses']:>6}{r['clean_distinct_streets']:>5}"
              f"{float(r['clean_street_coverage'])*100:>6.0f}%{r['mismatch_count']:>6}")
    return len(rows)


def main() -> None:
    validate_config()
    print("=" * 72)
    print("PART B — district authoritative address stats (zero Google calls)")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 72)
    apply_schema()
    # mismatches first — compute() denormalises their per-district count.
    populate_mismatches()
    compute()
    n = report()
    print(f"\nDistricts with stats: {n}")
    print(f"Finished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
