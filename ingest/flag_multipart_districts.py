"""
Flag remaining multi-part districts as review anomalies (Task B).

After the sliver-absorption pass (absorb_sliver_islands.py), a district may still
be composed of >1 polygon part because the extra parts are SUBSTANTIAL real
splits (not noise) that must NOT be auto-merged — e.g. Kúpeľná's 8.6 km² second
body, Šrobárova's twin 0.58/0.27 bodies, Sibírska's 1.5/1.1, Šmeralova's
0.79/0.46/0.30 bodies. The user wants these surfaced for human review, not
silently fixed.

This pass uses the EXISTING island/anomaly plumbing (no parallel system):

  1. Re-populate skolske_obvody.district_islands from the cleaned `geom`
     (one row per polygon part), preserving any is_demo=true seed rows.
  2. For each multi-part district: the largest part → status 'main_body';
     every other part → status 'unresolved_anomaly' with
     anomaly_type='multi_part_review'. The map's islandsGroup already renders
     status='unresolved_anomaly' parts as red dashed outlines, and the district
     detail page lists them.
  3. Insert ONE finding per multi-part district into skolske_obvody.findings
     (condition_code 'S2' — Topologické pokrytie, severity 'medium',
     tag 'geo:multipart'), so it appears in the Register nálezov. Idempotent:
     re-running deletes prior geo:multipart findings first.

Run:
    cd projects/skolske-obvody-44
    source <(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' /host-opt/frantiska-2/.env | sed 's/^/export /')
    python3 ingest/flag_multipart_districts.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from ingest.config import validate_config
from ingest.supabase_client import exec_sql, query_sql

PRESOV = "(SELECT id FROM skolske_obvody.municipalities WHERE slug = $$presov$$)"


# ---------------------------------------------------------------------------
# Step 1: re-populate district_islands from cleaned geom (preserve demo seeds)
# ---------------------------------------------------------------------------

def repopulate_islands() -> None:
    """Rebuild non-demo island rows from the cleaned geom.

    Demo seed rows (is_demo = true, e.g. the Šmeralova segregation island at
    index 99) are preserved untouched. Real rows are deleted and re-derived so
    island_index matches the cleaned geometry exactly.
    """
    print("\n[1] Re-populating district_islands from cleaned geom...")

    # Delete only non-demo Prešov rows
    r = exec_sql(f"""
        DELETE FROM skolske_obvody.district_islands di
        USING skolske_obvody.districts d
        WHERE di.district_id = d.id
          AND d.municipality_id = {PRESOV}
          AND COALESCE(di.is_demo, false) = false
    """)
    if not r.get("ok"):
        raise RuntimeError(f"island delete failed: {r.get('message')}")

    # Re-insert one row per polygon part, with per-part stats from house_geocodes
    r = exec_sql(f"""
        WITH dumped AS (
          SELECT d.id AS district_id,
                 (public.ST_Dump(d.geom)).path[1] - 1 AS island_index,
                 (public.ST_Dump(d.geom)).geom AS island_geom
          FROM skolske_obvody.districts d
          WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
        ),
        with_stats AS (
          SELECT du.district_id, du.island_index,
                 public.ST_Area(public.ST_Transform(du.island_geom, 32634)) AS area_m2,
                 du.island_geom AS geom,
                 array_remove(array_agg(DISTINCT hg.street ORDER BY hg.street), NULL) AS streets,
                 array_remove(array_agg(DISTINCT hg.house_number ORDER BY hg.house_number), NULL) AS house_numbers,
                 COUNT(hg.id) AS house_count_raw
          FROM dumped du
          LEFT JOIN skolske_obvody.house_geocodes hg
            ON hg.district_id = du.district_id
            AND hg.valid = true AND hg.geom IS NOT NULL
            AND public.ST_Contains(du.island_geom, hg.geom)
          GROUP BY du.district_id, du.island_index, du.island_geom
        )
        INSERT INTO skolske_obvody.district_islands
          (district_id, island_index, area_m2, geom, streets, house_numbers,
           house_count, street_count, is_demo)
        SELECT district_id, island_index, area_m2, geom, streets, house_numbers,
               house_count_raw::int, COALESCE(array_length(streets, 1), 0), false
        FROM with_stats
        ON CONFLICT (district_id, island_index) DO UPDATE SET
          area_m2 = EXCLUDED.area_m2,
          geom = EXCLUDED.geom,
          streets = EXCLUDED.streets,
          house_numbers = EXCLUDED.house_numbers,
          house_count = EXCLUDED.house_count,
          street_count = EXCLUDED.street_count
    """)
    if not r.get("ok"):
        raise RuntimeError(f"island repopulate failed: {r.get('message')}")
    print("  district_islands re-populated OK")


# ---------------------------------------------------------------------------
# Step 2: status — largest part = main_body, others = unresolved_anomaly
# ---------------------------------------------------------------------------

def set_statuses() -> None:
    print("\n[2] Setting island statuses (largest = main_body, rest = anomaly)...")

    # Largest part per district → main_body
    r = exec_sql(f"""
        WITH ranked AS (
          SELECT di.id,
                 row_number() OVER (PARTITION BY di.district_id ORDER BY di.area_m2 DESC) AS rn
          FROM skolske_obvody.district_islands di
          JOIN skolske_obvody.districts d ON d.id = di.district_id
          WHERE d.municipality_id = {PRESOV}
            AND COALESCE(di.is_demo, false) = false
        )
        UPDATE skolske_obvody.district_islands di
        SET status = 'main_body', anomaly_type = NULL
        FROM ranked
        WHERE di.id = ranked.id AND ranked.rn = 1
    """)
    if not r.get("ok"):
        raise RuntimeError(f"main_body update failed: {r.get('message')}")

    # All other (non-largest, non-demo) parts → unresolved_anomaly review flag
    r = exec_sql(f"""
        WITH ranked AS (
          SELECT di.id,
                 row_number() OVER (PARTITION BY di.district_id ORDER BY di.area_m2 DESC) AS rn
          FROM skolske_obvody.district_islands di
          JOIN skolske_obvody.districts d ON d.id = di.district_id
          WHERE d.municipality_id = {PRESOV}
            AND COALESCE(di.is_demo, false) = false
        )
        UPDATE skolske_obvody.district_islands di
        SET status = 'unresolved_anomaly',
            anomaly_type = 'multi_part_review',
            severity = 'medium'
        FROM ranked
        WHERE di.id = ranked.id AND ranked.rn > 1
    """)
    if not r.get("ok"):
        raise RuntimeError(f"anomaly update failed: {r.get('message')}")
    print("  statuses set OK")


# ---------------------------------------------------------------------------
# Step 3: one finding per multi-part district (Register nálezov)
# ---------------------------------------------------------------------------

def insert_findings() -> int:
    print("\n[3] Inserting one finding per multi-part district (tag geo:multipart)...")

    # Idempotent: clear prior geo:multipart findings first.
    # tag is per-district ('geo:multipart:<uuid>') because findings.tag carries a
    # global UNIQUE index — a single shared tag would collide across districts.
    r = exec_sql("""
        DELETE FROM skolske_obvody.findings WHERE tag LIKE $$geo:multipart:%$$
    """)
    if not r.get("ok"):
        raise RuntimeError(f"finding cleanup failed: {r.get('message')}")

    # Insert a finding for each district with >1 part, reusing that district's
    # existing S2 verdict (Topologické pokrytie) as verdict_id.
    r = exec_sql(f"""
        WITH multipart AS (
          SELECT d.id AS district_id, d.municipality_id,
                 public.ST_NumGeometries(d.geom) AS parts,
                 round((public.ST_Area(public.ST_Transform(
                   (SELECT (public.ST_Dump(d.geom)).geom
                    ORDER BY public.ST_Area((public.ST_Dump(d.geom)).geom) DESC
                    LIMIT 1), 32634)) / 1e6)::numeric, 2) AS biggest_km2
          FROM skolske_obvody.districts d
          WHERE d.municipality_id = {PRESOV}
            AND d.geom IS NOT NULL
            AND public.ST_NumGeometries(d.geom) > 1
        ),
        with_verdict AS (
          SELECT mp.*,
                 (SELECT v.id FROM skolske_obvody.verdicts v
                  WHERE v.district_id = mp.district_id AND v.condition_code = 'S2'
                  ORDER BY v.computed_at DESC LIMIT 1) AS verdict_id
          FROM multipart mp
        )
        INSERT INTO skolske_obvody.findings
          (verdict_id, district_id, municipality_id, condition_code, severity,
           status, evidence_text, is_demo, tag)
        SELECT verdict_id, district_id, municipality_id, 'S2', 'medium', 'open',
               'Obvod sa skladá z ' || parts || ' oddelených častí (najväčšia '
                 || biggest_km2 || ' km²). Podľa očakávania má byť školský obvod '
                 || 'jedna súvislá plocha — oddelené časti treba manuálne overiť '
                 || '(história zlúčených škôl, špecializované adresy, alebo chyba VZN).',
               false, $$geo:multipart:$$ || district_id::text
        FROM with_verdict
        WHERE verdict_id IS NOT NULL
    """)
    if not r.get("ok"):
        raise RuntimeError(f"finding insert failed: {r.get('message')}")

    rows = query_sql("""
        SELECT count(*) AS n FROM skolske_obvody.findings WHERE tag LIKE $$geo:multipart:%$$
    """)
    n = int(rows[0]["n"]) if rows else 0
    print(f"  inserted {n} multi-part findings")
    return n


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def summary() -> None:
    print("\n[verify] Multi-part districts now flagged:")
    rows = query_sql(f"""
        SELECT d.name,
               public.ST_NumGeometries(d.geom) AS parts,
               COUNT(di.id) FILTER (WHERE di.status = 'unresolved_anomaly'
                                    AND di.anomaly_type = 'multi_part_review') AS review_parts
        FROM skolske_obvody.districts d
        LEFT JOIN skolske_obvody.district_islands di ON di.district_id = d.id
        WHERE d.municipality_id = {PRESOV} AND d.geom IS NOT NULL
        GROUP BY d.name, d.geom
        HAVING public.ST_NumGeometries(d.geom) > 1
        ORDER BY parts DESC, d.name
    """)
    for r in rows:
        print(f"  {(r['name'] or '?')[:50]:<50} parts={r['parts']} "
              f"review_flags={r['review_parts']}")
    print(f"\n  Multi-part districts flagged: {len(rows)}")


def main() -> None:
    validate_config()
    print("=" * 70)
    print("Flag multi-part districts as review anomalies (Task B)")
    print("=" * 70)
    repopulate_islands()
    set_statuses()
    insert_findings()
    summary()
    print("\nDone.")


if __name__ == "__main__":
    main()
