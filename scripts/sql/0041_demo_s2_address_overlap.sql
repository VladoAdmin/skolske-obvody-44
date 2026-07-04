-- 0041_demo_s2_address_overlap.sql
-- Step 2 Sprint 1 — reinstate an ADDRESS-based Š2 demo scenario.
--
-- WHY
--   0040_streets_pivot.sql correctly retired the polygon-based overlap concept
--   (district_overlaps demo rows) and re-anchored engine/c_s2.py to the SAME
--   FULL ADDRESS (street + house number) claimed by two districts. But that
--   migration also deleted the only rows that ever produced a genuine
--   address-level duplicate (the "Ukážková ulica 1..8" house_geocodes demo
--   seed), so there is currently NO input data that lets c_s2 demonstrate a
--   FAIL. Real Prešov data has zero address overlaps (by construction), so
--   without an explicit demo input the "same full address in 2+ districts"
--   scenario is unrepresentable end to end.
--
-- WHAT
--   Insert ONE demo address into house_geocodes for EACH of two adjacent real
--   districts (Kúpeľná č. 2 / Sibírska č. 42 — same school_type=ZS,
--   teaching_language=SK, so c_s2's same-type filter matches them), using the
--   IDENTICAL street name + house number. Each row is_demo = TRUE with a
--   dedicated query_used tag so the provenance is explicit and the seed is
--   idempotent (delete-by-tag, re-insert).
--
--   This is deliberately NOT a shortcut: engine/c_s2.py does not read
--   district_demo_inputs at all for this condition — it runs its normal
--   real-data address query against house_geocodes. The demo input only
--   supplies data; the ENGINE decides FAIL from that data, exactly like any
--   real address would. That keeps Š2 honest per the streets-pivot mandate
--   ("shared street is not a finding; only the same full address is").
--
-- INVARIANTS
--   - Real (is_demo = FALSE) house_geocodes rows are never touched.
--   - Each demo row is placed INSIDE its own district polygon (ST_GeneratePoints)
--     so it never contradicts the district's real geometry.
--   - Idempotent: re-running deletes only rows with query_used =
--     'DEMO-s2-address-overlap-seed' before inserting.
--
-- Apply:  python3 scripts/apply_sql.py scripts/sql/0041_demo_s2_address_overlap.sql
-- Then:   python3 -m engine.runner   (with demo_mode_flag enabled — see docs)

-- PRE-INSERT VALIDATION (Sprint 1 review fix):
--   Fail loudly if the two target districts don't exist, or don't both carry
--   school_type='ZS' AND teaching_language='SK' — a silent no-op/partial insert
--   would leave a misleading half-seeded demo (e.g. one address with no overlap
--   partner) instead of a clear error.
DO $$
DECLARE
    v_count integer;
    v_mismatched integer;
BEGIN
    SELECT count(*) INTO v_count
    FROM skolske_obvody.districts
    WHERE name IN (
        'Základná škola, Kúpeľná č. 2',
        'Základná škola, Sibírska č. 42'
    );

    IF v_count <> 2 THEN
        RAISE EXCEPTION
            '0041 demo seed aborted: expected exactly 2 target districts (Kúpeľná č. 2, Sibírska č. 42), found %',
            v_count;
    END IF;

    SELECT count(*) INTO v_mismatched
    FROM skolske_obvody.districts
    WHERE name IN (
        'Základná škola, Kúpeľná č. 2',
        'Základná škola, Sibírska č. 42'
    )
    AND (school_type IS DISTINCT FROM 'ZS' OR teaching_language IS DISTINCT FROM 'SK');

    IF v_mismatched > 0 THEN
        RAISE EXCEPTION
            '0041 demo seed aborted: % target district(s) are not school_type=ZS/teaching_language=SK — the address-overlap demo requires a same-type pair',
            v_mismatched;
    END IF;
END $$;

DELETE FROM skolske_obvody.house_geocodes
WHERE query_used = 'DEMO-s2-address-overlap-seed';

WITH pair AS (
    SELECT id, name,
           row_number() OVER (ORDER BY name) AS rn
    FROM skolske_obvody.districts
    WHERE name IN (
        'Základná škola, Kúpeľná č. 2',
        'Základná škola, Sibírska č. 42'
    )
),
pts AS (
    SELECT
        pair.id AS district_id,
        (public.ST_Dump(
            public.ST_GeneratePoints(d.geom, 1, (4242 + pair.rn)::integer)
        )).geom AS pt
    FROM pair
    JOIN skolske_obvody.districts d ON d.id = pair.id
)
INSERT INTO skolske_obvody.house_geocodes
    (id, district_id, street, house_number, query_used, status,
     lat, lon, formatted_address, geom, valid, is_demo, created_at)
SELECT
    gen_random_uuid(),
    pts.district_id,
    'Ukážková adresa (prekryv obvodov)',
    '7',
    'DEMO-s2-address-overlap-seed',
    'OK',
    public.ST_Y(pts.pt),
    public.ST_X(pts.pt),
    'Ukážková adresa (prekryv obvodov) 7 — demo vstup pre Š2',
    public.ST_SetSRID(pts.pt, 4326),
    TRUE,
    TRUE,
    now()
FROM pts;

-- Verify: exactly one address-overlap pair, matching engine/c_s2.py's own
-- same-street+house-number query.
SELECT
    h1.district_id AS district_a,
    h2.district_id AS district_b,
    h1.street,
    h1.house_number
FROM skolske_obvody.house_geocodes h1
JOIN skolske_obvody.house_geocodes h2
  ON h1.id <> h2.id
 AND h1.district_id <> h2.district_id
 AND lower(trim(h1.street)) = lower(trim(h2.street))
 AND trim(h1.house_number) = trim(h2.house_number)
WHERE h1.query_used = 'DEMO-s2-address-overlap-seed';
