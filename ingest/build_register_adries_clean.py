"""
STEP 2 — build the clean canonical address set.

Derives skolske_obvody.register_adries_clean from the authoritative register
(skolske_obvody.register_adries, 16307 rows) by:

  * keeping only habitable    (obyvatelna = TRUE)
  * keeping only NOT withdrawn (vyradena   = FALSE)
  * normalising the street name with the SAME NORM the geometry build uses
    (lower + unaccent + strip leading "Ulica " + drop "č."/dots + expand
    "Arm. gen." + collapse whitespace)  -> ulica_norm
  * trimming súpisné / orientačné číslo (btrim)
  * dropping exact duplicates on (ulica_norm, supisne_cislo, orientacne_cislo)

Additive only: writes a new table + public view (scripts/sql/0026...). Does not
touch the raw register or the legal Š1–Š3 verdict views.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/build_register_adries_clean.py
"""

from __future__ import annotations

import sys
from datetime import datetime

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

# SAME normalisation family as build_street_districts.py NORM(), with the outer
# btrim used by compute_district_address_stats.py so trailing-dot register
# variants ("Veterná.") fold to the VZN street ("Veterná").
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
    print("\n[schema] Applying scripts/sql/0026_register_adries_clean.sql ...")
    with open("scripts/sql/0026_register_adries_clean.sql", encoding="utf-8") as fh:
        sql = fh.read()
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"schema apply failed: {r.get('message')}")
    print("  schema OK")


def build() -> None:
    print("\n[build] Rebuilding register_adries_clean (truncate + reload)...")
    # DISTINCT ON collapses exact duplicates on the clean key, keeping the lowest
    # source id as the representative row. unaccent/normalisation is computed in
    # SQL so the clean key is byte-identical to the geometry build's join key.
    sql = f"""
TRUNCATE skolske_obvody.register_adries_clean RESTART IDENTITY;
INSERT INTO skolske_obvody.register_adries_clean
  (register_id, mesto, cast_mesta, ulica, ulica_norm,
   supisne_cislo, orientacne_cislo, adresa, psc, mestska_oblast)
SELECT DISTINCT ON (ulica_norm, supisne_cislo, orientacne_cislo)
  id, mesto, cast_mesta, ulica, ulica_norm,
  supisne_cislo, orientacne_cislo, adresa, psc, mestska_oblast
FROM (
  SELECT
    ra.id,
    ra.mesto,
    ra.cast_mesta,
    ra.ulica,
    {NORM('ra.ulica')}            AS ulica_norm,
    btrim(ra.supisne_cislo)       AS supisne_cislo,
    btrim(ra.orientacne_cislo)    AS orientacne_cislo,
    ra.adresa,
    ra.psc,
    ra.mestska_oblast
  FROM skolske_obvody.register_adries ra
  WHERE ra.obyvatelna = TRUE
    AND ra.vyradena = FALSE
    AND {NORM('ra.ulica')} <> ''
) src
ORDER BY ulica_norm, supisne_cislo, orientacne_cislo, id;
"""
    r = exec_sql(sql)
    if not r.get("ok"):
        raise RuntimeError(f"build failed: {r.get('message')}")
    print("  clean table written OK")


def report() -> dict:
    total = int(query_sql(
        "SELECT count(*) n FROM skolske_obvody.register_adries")[0]["n"])

    # Drop reasons (counted on the raw register, mutually reported as filters).
    drop = query_sql(f"""
      SELECT
        count(*) FILTER (WHERE obyvatelna IS NOT TRUE)                      AS not_habitable,
        count(*) FILTER (WHERE obyvatelna = TRUE AND vyradena IS NOT FALSE) AS withdrawn,
        count(*) FILTER (WHERE obyvatelna = TRUE AND vyradena = FALSE
                            AND {NORM('ulica')} = '')                       AS empty_street
      FROM skolske_obvody.register_adries
    """)[0]

    kept = int(query_sql(
        "SELECT count(*) n FROM skolske_obvody.register_adries_clean")[0]["n"])
    distinct_streets = int(query_sql(
        "SELECT count(DISTINCT ulica_norm) n FROM skolske_obvody.register_adries_clean")[0]["n"])

    # Rows that passed the habitable/withdrawn/non-empty filters but collapsed as
    # exact duplicates on the clean key.
    eligible = total - int(drop["not_habitable"]) - int(drop["withdrawn"]) - int(drop["empty_street"])
    dup_dropped = eligible - kept

    print("\n" + "=" * 64)
    print("STEP 2 — CLEAN ADDRESS SET")
    print("=" * 64)
    print(f"  input register rows        : {total}")
    print(f"  dropped — not habitable    : {drop['not_habitable']}")
    print(f"  dropped — withdrawn        : {drop['withdrawn']}")
    print(f"  dropped — empty street     : {drop['empty_street']}")
    print(f"  dropped — exact duplicates : {dup_dropped}")
    print(f"  KEPT (clean canonical)     : {kept}")
    print(f"  distinct clean streets     : {distinct_streets}")
    return {
        "input": total,
        "not_habitable": int(drop["not_habitable"]),
        "withdrawn": int(drop["withdrawn"]),
        "empty_street": int(drop["empty_street"]),
        "dup_dropped": dup_dropped,
        "kept": kept,
        "distinct_streets": distinct_streets,
    }


def main() -> dict:
    validate_config()
    print("=" * 64)
    print("STEP 2 — build clean canonical address set")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 64)
    apply_schema()
    build()
    stats = report()
    print(f"\nFinished: {datetime.now().isoformat()}")
    return stats


if __name__ == "__main__":
    main()
