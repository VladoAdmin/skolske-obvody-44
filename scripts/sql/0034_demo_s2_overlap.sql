-- 0034_demo_s2_overlap.sql
-- Part B — S2 Topológia DEMO. Real Prešov geometry has NO overlaps (all districts
-- geometry_confidence='high', zero >1 m² overlaps), so a topology violation can
-- ONLY be shown as a clearly-flagged DEMO.
--
-- We insert ONE explicit demo overlap polygon (is_demo=TRUE) along the shared
-- boundary of two real adjacent districts (Kúpeľná ↔ Sibírska). This is a separate
-- illustration layer:
--   * real districts.geom is NOT modified,
--   * the real address↔district assignment is therefore unchanged,
--   * the S2 verdict stays PASS (clean real geometry) and the semafor is NOT
--     degraded by demo data (mock never drives the traffic light),
--   * the engine emits a clearly-badged DEMO S2 finding from this layer and the
--     map renders the demo overlap polygon.
--
-- Idempotent: clears prior demo overlaps first.

DELETE FROM skolske_obvody.district_overlaps WHERE is_demo = TRUE;

WITH pair AS (
    SELECT
        a.id AS a_id, a.geom AS a_geom,
        b.id AS b_id, b.geom AS b_geom
    FROM skolske_obvody.districts a
    JOIN skolske_obvody.districts b ON a.id < b.id
    WHERE a.name = 'Základná škola, Kúpeľná č. 2'
      AND b.name = 'Základná škola, Sibírska č. 42'
),
strip AS (
    -- A small overlap strip: buffer a central chunk of the shared boundary by ~25 m.
    -- This polygon straddles both districts → a visible, plausible "double coverage".
    SELECT
        pair.a_id, pair.b_id,
        public.ST_Transform(
            public.ST_Buffer(
                public.ST_Transform(
                    public.ST_LineSubstring(
                        public.ST_LineMerge(
                            public.ST_Intersection(
                                public.ST_Boundary(pair.a_geom),
                                public.ST_Boundary(pair.b_geom)
                            )
                        ),
                        0.40, 0.55
                    ),
                    32634
                ),
                25.0
            ),
            4326
        ) AS geom
    FROM pair
)
INSERT INTO skolske_obvody.district_overlaps
    (id, district_a_id, district_b_id, overlap_geom, overlap_area_m2, severity, tag, is_demo)
SELECT
    gen_random_uuid(),
    strip.a_id,
    strip.b_id,
    strip.geom,
    public.ST_Area(public.ST_Transform(strip.geom, 32634)),
    'high',
    'demo:s2',
    TRUE
FROM strip
WHERE strip.geom IS NOT NULL
  AND NOT public.ST_IsEmpty(strip.geom);
