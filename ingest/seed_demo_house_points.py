"""
Batch-4b demo address density — fill sparse districts with clearly-inside points.

WHY
  After the containment reassignment (reassign_geocode_districts.py), several
  districts have very few or zero geocoded address dots, so the map reads as
  empty there even though every shown dot is now correctly inside its district.
  This is purely cosmetic demo density — NOT a verdict input.

WHAT
  For each Prešov district with fewer than TARGET visible house points, add
  (TARGET - current) demo-flagged points generated with public.ST_GeneratePoints
  INSIDE the district polygon, so they are guaranteed contained (ST_Covers = TRUE
  by construction). Each row is is_demo = TRUE and carries a demo street label.

INVARIANTS
  - is_demo = TRUE on every seeded row (demo-flagged, never silent).
  - Generated strictly inside the polygon → containment stays 0-outside.
  - Does NOT touch district_demo_inputs → S1 / all verdicts unchanged.
  - Idempotent: only tops up districts below TARGET; existing real points kept.
    Re-runs delete prior demo points first so density never compounds.

Run:
    cd projects/skolske-obvody-44
    python3 ingest/seed_demo_house_points.py
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
TARGET = 8  # minimum visible house dots per district for a populated-looking map


def _check(res: dict, ctx: str) -> None:
    if not res.get("ok"):
        raise RuntimeError(f"{ctx} failed: {res.get('message')}")


def main() -> None:
    validate_config()
    print(f"\n{'='*64}\nSeed demo house points (density top-up) — Prešov\n{'='*64}")

    # Reset prior demo seed so density does not compound on re-run.
    _check(
        exec_sql(
            "DELETE FROM skolske_obvody.house_geocodes "
            "WHERE is_demo = TRUE AND query_used = 'DEMO-density-seed'"
        ),
        "reset prior demo seed",
    )

    # Current visible (geom inside own district) house count per district.
    rows = query_sql(f"""
        SELECT d.id,
               d.name,
               count(h.id) FILTER (
                   WHERE h.geom IS NOT NULL AND public.ST_Covers(d.geom, h.geom)
               ) AS visible
        FROM skolske_obvody.districts d
        LEFT JOIN skolske_obvody.house_geocodes h ON h.district_id = d.id
        WHERE d.municipality_id = '{PRESOV_MUN_ID}'
        GROUP BY d.id, d.name
        ORDER BY d.name
    """)

    seeded_total = 0
    for idx, r in enumerate(rows):
        did = r["id"]
        seed_base = 1000 + idx * 100  # deterministic per-district PRNG seed
        visible = int(r["visible"])
        need = TARGET - visible
        if need <= 0:
            print(f"  {r['name'][:44]:<44} visible={visible} (no seed)")
            continue

        # Generate `need` points strictly inside the district polygon. Each becomes
        # a demo-flagged house_geocode with a unique street label so the UNIQUE
        # (district_id, street, house_number) constraint never collides.
        _check(
            exec_sql(f"""
                INSERT INTO skolske_obvody.house_geocodes
                    (id, district_id, street, house_number, query_used, status,
                     lat, lon, formatted_address, geom, valid, is_demo, created_at)
                SELECT
                    gen_random_uuid(),
                    '{did}',
                    'Ukážková ulica ' || gs.n,
                    gs.n::text,
                    'DEMO-density-seed',
                    'OK',
                    public.ST_Y(p.pt),
                    public.ST_X(p.pt),
                    'Ukážková adresa (demo)',
                    public.ST_SetSRID(p.pt, 4326),
                    TRUE,
                    TRUE,
                    now()
                FROM generate_series(1, {need}) AS gs(n)
                JOIN LATERAL (
                    SELECT (public.ST_Dump(
                        public.ST_GeneratePoints(d.geom, 1, {seed_base} + gs.n)
                    )).geom AS pt
                    FROM skolske_obvody.districts d
                    WHERE d.id = '{did}'
                ) p ON TRUE
            """),
            f"seed demo points {r['name'][:30]}",
        )
        seeded_total += need
        print(f"  {r['name'][:44]:<44} visible={visible} → seeded +{need}")

    print(f"\n  Total demo points seeded: {seeded_total}")

    # --- Pa illustration consistency ---------------------------------------
    # The Pa (>2 km) illustration draws a line from the school to the FARTHEST
    # contained address. Its demo verdict is seeded via
    # district_demo_inputs.pa_max_distance_m. After containment reassignment a
    # district's real farthest contained house can be < 2 km, so the line (and
    # its legend) would vanish even though the verdict is FAIL — an inconsistency.
    # For each district whose pa_max_distance_m > 2000 m but whose real farthest
    # contained house is below that, seed ONE demo-flagged "far address" at an
    # inside point whose school-distance is closest to pa_max_distance_m, so the
    # illustration matches the seeded verdict and stays inside the polygon.
    pa_rows = query_sql(f"""
        SELECT d.id, d.name, di.pa_max_distance_m,
               round(COALESCE(max(public.ST_Distance(
                   public.ST_Transform(h.geom, 32634),
                   public.ST_Transform(s.geom, 32634))), 0)::numeric, 0) AS real_far_m
        FROM skolske_obvody.districts d
        JOIN skolske_obvody.district_demo_inputs di ON di.district_id = d.id
        JOIN skolske_obvody.schools s ON s.id = d.school_id
        LEFT JOIN skolske_obvody.house_geocodes h
               ON h.district_id = d.id AND h.geom IS NOT NULL
        WHERE d.municipality_id = '{PRESOV_MUN_ID}'
          AND di.pa_max_distance_m IS NOT NULL
          AND di.pa_max_distance_m > 2000
        GROUP BY d.id, d.name, di.pa_max_distance_m
    """)
    pa_seeded = 0
    for r in pa_rows:
        target = float(r["pa_max_distance_m"])
        real_far = float(r["real_far_m"] or 0)
        if real_far >= target - 50:
            print(f"  Pa {r['name'][:40]:<40} real_far={real_far}m ≥ target — no Pa seed")
            continue
        did = r["id"]
        # Remove any prior Pa-far seed for this district (idempotent).
        _check(
            exec_sql(
                f"DELETE FROM skolske_obvody.house_geocodes "
                f"WHERE district_id = '{did}' AND query_used = 'DEMO-pa-far-seed'"
            ),
            "reset prior pa seed",
        )
        # Pick the inside-polygon point (of a dense candidate set) whose distance
        # to the school is closest to the target Pa distance.
        _check(
            exec_sql(f"""
                INSERT INTO skolske_obvody.house_geocodes
                    (id, district_id, street, house_number, query_used, status,
                     lat, lon, formatted_address, geom, valid, is_demo, created_at)
                SELECT
                    gen_random_uuid(), '{did}',
                    'Ukážková ulica – vzdialená adresa', 'Pa',
                    'DEMO-pa-far-seed', 'OK',
                    public.ST_Y(c.pt), public.ST_X(c.pt),
                    'Ukážková vzdialená adresa (demo, Pa)',
                    public.ST_SetSRID(c.pt, 4326), TRUE, TRUE, now()
                FROM (
                    SELECT p.pt
                    FROM (
                        SELECT (public.ST_Dump(
                            public.ST_GeneratePoints(d.geom, 3000, 7)
                        )).geom AS pt
                        FROM skolske_obvody.districts d WHERE d.id = '{did}'
                    ) p,
                    skolske_obvody.districts dd
                    JOIN skolske_obvody.schools s ON s.id = dd.school_id
                    WHERE dd.id = '{did}'
                    ORDER BY abs(public.ST_Distance(
                        public.ST_Transform(p.pt, 32634),
                        public.ST_Transform(s.geom, 32634)) - {target})
                    LIMIT 1
                ) c
            """),
            f"seed Pa far point {r['name'][:30]}",
        )
        pa_seeded += 1
        # Report the achieved distance.
        ach = query_sql(f"""
            SELECT round(public.ST_Distance(
                public.ST_Transform(h.geom, 32634),
                public.ST_Transform(s.geom, 32634))::numeric, 0) AS m
            FROM skolske_obvody.house_geocodes h
            JOIN skolske_obvody.districts d ON d.id = h.district_id
            JOIN skolske_obvody.schools s ON s.id = d.school_id
            WHERE h.query_used = 'DEMO-pa-far-seed' AND h.district_id = '{did}'
        """)
        got = ach[0]["m"] if ach else "?"
        print(f"  Pa {r['name'][:40]:<40} target={int(target)}m real={int(real_far)}m → seeded far point @ {got}m")
    print(f"  Pa far points seeded: {pa_seeded}")

    # Verify: still 0 outside, and every district now >= TARGET visible.
    out = query_sql(f"""
        SELECT count(*) n FROM skolske_obvody.house_geocodes h
        JOIN skolske_obvody.districts d ON d.id = h.district_id
        WHERE h.geom IS NOT NULL AND NOT public.ST_Covers(d.geom, h.geom)
    """)
    print(f"  house_geocodes outside assigned district: {out[0]['n']} (must be 0)")
    if int(out[0]["n"]) != 0:
        raise RuntimeError("seeding produced points outside their district")
    print("\nDone. Next: python3 -m engine.runner (verify distribution unchanged).\n")


if __name__ == "__main__":
    main()
