"""
Batch-4b address↔district containment fix.

WHY
  The clean-demo Voronoi rebuild (rebuild_clean_demo_geom.py) produced tidy
  single-polygon districts, but the geocoded address/street points kept their
  OLD district_id. Result: 465/513 house_geocodes and 245/423 street_geocodes
  fell OUTSIDE the polygon of the district they were attributed to — every
  rendered address dot sat in the wrong obvod. This is the classic
  "area-invariant passes but addresses are wrong" trap.

FIX
  Reassign each geocoded point to the district whose CLEAN polygon spatially
  CONTAINS it (public.ST_Covers(d.geom, p.geom)). For Prešov every point is
  covered by exactly one district (verified: 0 multi-cover, 0 orphans), so a
  pure containment reassignment is exact and needs no nearest-fallback.

  Points outside the Prešov municipality entirely (none today) would be left
  untouched — they are not rendered by the so_house_points / so_street_geocodes
  views (which inner-join Prešov districts) so they never become orphan dots.

SAFETY / DEMO INVARIANTS
  - This ONLY moves point→district attribution to match geometry. It does NOT
    touch district_demo_inputs, so the S1 demo verdict (seeded via
    district_demo_inputs.s1_wrong_district, independent of
    house_geocodes.district_id) is UNCHANGED. Re-run `python3 -m engine.runner`
    to confirm the 6/2/4 distribution is unchanged.
  - MRK locality points (so_mrk_localities) are derived by ST_Intersects at
    query time (no stored district_id) and are already self-consistent
    (0 intersect-but-not-covered) — left as-is.

Run:
    cd projects/skolske-obvody-44
    python3 ingest/reassign_geocode_districts.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, ".")


def _load_env() -> None:
    env_path = ".env.local"
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

from ingest.config import validate_config  # noqa: E402
from ingest.supabase_client import exec_sql, query_sql  # noqa: E402

PRESOV_MUN_ID = "e74cc008-e6e3-4b4d-abae-0c62d240ba01"


def _check(res: dict, ctx: str) -> None:
    if not res.get("ok"):
        raise RuntimeError(f"{ctx} failed: {res.get('message')}")


def _outside_count(table: str) -> int:
    rows = query_sql(f"""
        SELECT count(*) AS n
        FROM skolske_obvody.{table} g
        JOIN skolske_obvody.districts d ON d.id = g.district_id
        WHERE g.geom IS NOT NULL
          AND NOT public.ST_Covers(d.geom, g.geom)
    """)
    return int(rows[0]["n"]) if rows else -1


def _multi_cover_count(table: str) -> int:
    rows = query_sql(f"""
        SELECT count(*) AS n FROM (
            SELECT g.id
            FROM skolske_obvody.{table} g
            JOIN skolske_obvody.districts d
              ON d.municipality_id = '{PRESOV_MUN_ID}'
             AND public.ST_Covers(d.geom, g.geom)
            WHERE g.geom IS NOT NULL
            GROUP BY g.id
            HAVING count(*) > 1
        ) s
    """)
    return int(rows[0]["n"]) if rows else -1


def _orphan_count(table: str) -> int:
    rows = query_sql(f"""
        SELECT count(*) AS n
        FROM skolske_obvody.{table} g
        WHERE g.geom IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM skolske_obvody.districts d
            WHERE d.municipality_id = '{PRESOV_MUN_ID}'
              AND public.ST_Covers(d.geom, g.geom)
          )
    """)
    return int(rows[0]["n"]) if rows else -1


def _dedupe_collisions(table: str, key_cols: str) -> int:
    """
    A UNIQUE(district_id, <key_cols>) constraint means two geocode rows that, after
    containment reassignment, land in the SAME target district with the SAME
    street/house_number are the SAME real address geocoded twice. Keep exactly one
    per (target_district, key) and delete the surplus duplicates BEFORE the UPDATE
    so the reassignment cannot violate the constraint. Deterministic keep: prefer
    valid=TRUE (house_geocodes), then lowest id. Returns rows deleted.
    """
    valid_pref = "(g.valid IS NOT TRUE)::int," if table == "house_geocodes" else ""
    # Count surplus rows first (exec_sql does not return a rowcount).
    cnt = query_sql(f"""
        SELECT count(*) AS n FROM (
            SELECT row_number() OVER (
                       PARTITION BY d.id, {key_cols}
                       ORDER BY {valid_pref} g.id
                   ) AS rn
            FROM skolske_obvody.{table} g
            JOIN skolske_obvody.districts d
              ON d.municipality_id = '{PRESOV_MUN_ID}'
             AND public.ST_Covers(d.geom, g.geom)
            WHERE g.geom IS NOT NULL
        ) s WHERE rn > 1
    """)
    n_surplus = int(cnt[0]["n"]) if cnt else 0
    res = exec_sql(f"""
        WITH tgt AS (
            SELECT g.id AS gid,
                   d.id AS did,
                   {', '.join('g.' + c for c in [c.strip() for c in key_cols.split(',')])},
                   row_number() OVER (
                       PARTITION BY d.id, {key_cols}
                       ORDER BY {valid_pref} g.id
                   ) AS rn
            FROM skolske_obvody.{table} g
            JOIN skolske_obvody.districts d
              ON d.municipality_id = '{PRESOV_MUN_ID}'
             AND public.ST_Covers(d.geom, g.geom)
            WHERE g.geom IS NOT NULL
        )
        DELETE FROM skolske_obvody.{table} t
        USING tgt
        WHERE t.id = tgt.gid AND tgt.rn > 1
    """)
    _check(res, f"dedupe {table}")
    return n_surplus


def reassign(table: str, key_cols: str) -> None:
    print(f"\n--- {table} ---")
    before = _outside_count(table)
    multi = _multi_cover_count(table)
    orphan = _orphan_count(table)
    print(f"  before: outside={before}  multi_cover={multi}  orphan(no Prešov district)={orphan}")

    if multi > 0:
        raise RuntimeError(
            f"{table}: {multi} points are covered by >1 district polygon — "
            "containment reassignment is ambiguous; aborting."
        )

    # Orphans: points covered by NO Prešov district (mis-geocoded streets matched
    # to a same-named street elsewhere, up to tens of km away). Containment cannot
    # place them, and the so_* views inner-join districts → leaving them would
    # render a dot outside every polygon. district_id is NOT NULL, so we DELETE
    # these bad geocodes outright (they are not real Prešov addresses).
    if orphan > 0:
        _check(
            exec_sql(f"""
                DELETE FROM skolske_obvody.{table} g
                WHERE g.geom IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM skolske_obvody.districts d
                    WHERE d.municipality_id = '{PRESOV_MUN_ID}'
                      AND public.ST_Covers(d.geom, g.geom)
                  )
            """),
            f"drop orphans {table}",
        )
        print(f"  orphans deleted (mis-geocoded, outside all Prešov districts): {orphan} rows")

    deleted = _dedupe_collisions(table, key_cols)
    print(f"  deduped (same address geocoded twice into one target district): {deleted} rows deleted")

    # Reassign district_id to the single Prešov district whose polygon covers the
    # point. Orphans (covered by no district) are left untouched; the so_* views
    # inner-join districts so they will not render as dots outside all districts.
    _check(
        exec_sql(f"""
            UPDATE skolske_obvody.{table} g
            SET district_id = sub.did
            FROM (
                SELECT g2.id AS gid, d.id AS did
                FROM skolske_obvody.{table} g2
                JOIN skolske_obvody.districts d
                  ON d.municipality_id = '{PRESOV_MUN_ID}'
                 AND public.ST_Covers(d.geom, g2.geom)
                WHERE g2.geom IS NOT NULL
            ) sub
            WHERE g.id = sub.gid
              AND g.district_id IS DISTINCT FROM sub.did
        """),
        f"reassign {table}",
    )

    after = _outside_count(table)
    print(f"  after:  outside={after}")
    if after != 0:
        raise RuntimeError(f"{table}: still {after} points outside assigned district")


def main() -> None:
    validate_config()
    print(f"\n{'='*64}\nReassign geocode points to containing district — Prešov\n{'='*64}")
    reassign("house_geocodes", "street, house_number")
    reassign("street_geocodes", "street")
    print("\nDone. Next: python3 -m engine.runner (verify distribution unchanged).\n")


if __name__ == "__main__":
    main()
