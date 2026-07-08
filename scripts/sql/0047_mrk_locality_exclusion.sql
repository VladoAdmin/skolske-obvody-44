-- 0047_mrk_locality_exclusion.sql
-- VLA-16 — MRK localities render as bare points on the map; client wants an
-- area/hatch rendering plus a visible "excluded into a different, more
-- distant school district" link for the P-e demo scenario (Šrobárova).
--
-- Why NOT so_mrk_overlays for the per-locality area: that view intentionally
-- exposes the OBEC-LEVEL Atlas MRK polygon (see 0038's own comment) — using it
-- per locality would reintroduce the item-14 bug ("whole city lights up").
-- The area rendering instead buffers each locality POINT client-side; this
-- migration only adds the data needed for the exclusion link.
--
-- 1. mrk_buildings gets a nullable assigned_district_id: the district a
--    locality is administratively assigned to. NULL for every existing row
--    (real or demo) — no behavioural change to c_pe.py, which never reads
--    this column. Only the new demo row below sets it.
-- 2. so_mrk_localities (0038) is extended with the GEOGRAPHIC district (whichever
--    real district polygon actually contains the point, via ST_Within — same
--    predicate c_pe.py uses) alongside the ASSIGNED district + its school, so
--    the client can detect a mismatch and draw the link without any further
--    geometry math.
-- 3. One DEMO building is added: point real-computed as ST_PointOnSurface of
--    the Prostějovská district (a real Prešov district touching Šrobárova),
--    assigned_district_id = Šrobárova. This is a genuine geometric fact (the
--    point truly sits inside Prostějovská) paired with a fabricated
--    administrative assignment — flagged is_demo=TRUE throughout, DEMO badge
--    applies. It does not touch district_demo_inputs.pe_mrk_signal, which
--    already decisively drives the Šrobárova Pe SIGNAL.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS; demo delete scoped to this migration's
-- own provenance tag so it never touches the 0032 inclusion-demo rows.

ALTER TABLE skolske_obvody.mrk_buildings
  ADD COLUMN IF NOT EXISTS assigned_district_id uuid REFERENCES skolske_obvody.districts(id);

DELETE FROM skolske_obvody.mrk_buildings
WHERE is_demo = TRUE AND provenance->>'layer' = 'DEMO vyčlenenie';

INSERT INTO skolske_obvody.mrk_buildings (id, obec, geom, is_demo, assigned_district_id, provenance)
SELECT
    gen_random_uuid(),
    'Prešov',
    public.ST_PointOnSurface(z.geom),
    TRUE,
    y.id,
    jsonb_build_object(
        'layer', 'DEMO vyčlenenie',
        'note', 'DEMO: lokalita geograficky patrí do obvodu ' || z.name ||
                ', VZN ju napriek tomu priraďuje do obvodu ' || y.name ||
                ' — ukážka vyčlenenia do vzdialenejšieho obvodu (§ 44 ods. 8 písm. e)'
    )
FROM skolske_obvody.districts y, skolske_obvody.districts z
WHERE y.name = 'Základná škola, Šrobárova č. 20'
  AND z.name = 'Základná škola, Prostějovská č. 38';

CREATE OR REPLACE VIEW public.so_mrk_localities AS
SELECT
    b.id,
    b.obec                                     AS obec_name,
    public.ST_AsGeoJSON(b.geom)::jsonb         AS geom_geojson,
    COALESCE(b.is_demo, FALSE)                 AS is_demo,
    geo_d.id                                   AS geographic_district_id,
    geo_d.name                                 AS geographic_district_name,
    public.ST_Distance(
        public.ST_Transform(b.geom, 3857),
        public.ST_Transform(geo_s.geom, 3857)
    )                                           AS geographic_distance_m,
    asn_d.id                                    AS assigned_district_id,
    asn_d.name                                  AS assigned_district_name,
    public.ST_AsGeoJSON(asn_s.geom)::jsonb     AS assigned_school_geojson,
    public.ST_Distance(
        public.ST_Transform(b.geom, 3857),
        public.ST_Transform(asn_s.geom, 3857)
    )                                           AS assigned_distance_m
FROM skolske_obvody.mrk_buildings b
LEFT JOIN skolske_obvody.districts geo_d ON public.ST_Within(b.geom, geo_d.geom)
LEFT JOIN skolske_obvody.schools geo_s ON geo_s.id = geo_d.school_id
LEFT JOIN skolske_obvody.districts asn_d ON asn_d.id = b.assigned_district_id
LEFT JOIN skolske_obvody.schools asn_s ON asn_s.id = asn_d.school_id
WHERE EXISTS (
    SELECT 1
    FROM skolske_obvody.districts d
    WHERE d.municipality_id = (
        SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov'
    )
      AND public.ST_Intersects(b.geom, d.geom)
);

GRANT SELECT ON public.so_mrk_localities TO anon, authenticated;
