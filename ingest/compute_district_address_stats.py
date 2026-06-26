"""
Sprint register-geocode-confidence — PART B (zero API cost).

Compute per-district authoritative address statistics by joining the
authoritative Prešov address register (skolske_obvody.register_adries,
habitable rows only) to districts via the VZN street->district mapping
(skolske_obvody.vzn_street_ranges).

Per district:
  - habitable_addresses     : # authoritative habitable addresses on this
                              district's VZN streets
  - register_streets        : distinct register streets matched to those VZN streets
  - vzn_streets             : distinct VZN streets assigned to this district
  - vzn_streets_in_register : how many of those VZN streets exist in the register
  - street_coverage         : vzn_streets_in_register / vzn_streets  (0..1)
                              -> the data-confidence indicator surfaced in the UI.

Street name matching uses the same normalisation as build_street_districts.py
(strip diacritics/Ulica/dots, expand the one abbreviation) + a trailing-trim so
register variants like "Veterná." match the VZN "Veterná".

A register street that appears in the VZN ranges of >1 district is attributed to
EACH of those districts (the address-level split is exactly what geocoding
resolves; for the count signal both districts legitimately list the street).

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


def apply_schema() -> None:
    print("\n[schema] Applying scripts/sql/0023_register_geocode_and_stats.sql ...")
    with open("scripts/sql/0023_register_geocode_and_stats.sql", encoding="utf-8") as fh:
        sql = fh.read()
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"schema apply failed: {r.get('message')}")
    print("  schema OK")


def compute() -> None:
    print("\n[compute] Per-district authoritative address stats (no API calls)...")
    # vzn: distinct (district, normalised street) the VZN assigns.
    # reg: habitable register rows with normalised street.
    # Per (district, vzn street) we LEFT JOIN register rows on the normalised
    # name; counting register rows gives habitable_addresses, and counting
    # district VZN streets that have >=1 register row gives coverage.
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
joined AS (
  SELECT v.district_id, v.nname AS vzn_nname,
         r.id AS reg_id, r.ulica AS reg_ulica
  FROM vzn v
  LEFT JOIN reg r ON r.nname = v.nname
),
agg AS (
  SELECT
    district_id,
    count(reg_id)                                      AS habitable_addresses,
    count(DISTINCT reg_ulica)                          AS register_streets,
    count(DISTINCT vzn_nname)                          AS vzn_streets,
    count(DISTINCT vzn_nname) FILTER (WHERE reg_id IS NOT NULL) AS vzn_streets_in_register
  FROM joined
  GROUP BY district_id
)
INSERT INTO skolske_obvody.district_address_stats
  (district_id, habitable_addresses, register_streets, vzn_streets,
   vzn_streets_in_register, street_coverage, computed_at)
SELECT
  district_id,
  habitable_addresses,
  register_streets,
  vzn_streets,
  vzn_streets_in_register,
  CASE WHEN vzn_streets > 0
       THEN round((vzn_streets_in_register::numeric / vzn_streets), 4)
       ELSE 0 END,
  now()
FROM agg
ON CONFLICT (district_id) DO UPDATE SET
  habitable_addresses     = EXCLUDED.habitable_addresses,
  register_streets        = EXCLUDED.register_streets,
  vzn_streets             = EXCLUDED.vzn_streets,
  vzn_streets_in_register = EXCLUDED.vzn_streets_in_register,
  street_coverage         = EXCLUDED.street_coverage,
  computed_at             = EXCLUDED.computed_at
"""
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"compute failed: {r.get('message')}")
    print("  stats written OK")


def report() -> int:
    rows = query_sql(f"""
        SELECT d.name,
               s.habitable_addresses, s.register_streets,
               s.vzn_streets, s.vzn_streets_in_register, s.street_coverage
        FROM skolske_obvody.district_address_stats s
        JOIN skolske_obvody.districts d ON d.id = s.district_id
        WHERE d.municipality_id = {PRESOV}
        ORDER BY s.habitable_addresses DESC
    """)
    print("\n" + "=" * 72)
    print("PER-DISTRICT AUTHORITATIVE ADDRESS STATS")
    print("=" * 72)
    print(f"{'District':<46}{'addr':>6}{'str':>5}{'vzn':>5}{'inReg':>6}{'cov':>7}")
    for r in rows:
        print(f"{(r['name'] or '?')[:45]:<46}"
              f"{r['habitable_addresses']:>6}{r['register_streets']:>5}"
              f"{r['vzn_streets']:>5}{r['vzn_streets_in_register']:>6}"
              f"{float(r['street_coverage'])*100:>6.0f}%")
    return len(rows)


def main() -> None:
    validate_config()
    print("=" * 72)
    print("PART B — district authoritative address stats (zero Google calls)")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 72)
    apply_schema()
    compute()
    n = report()
    print(f"\nDistricts with stats: {n}")
    print(f"Finished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
