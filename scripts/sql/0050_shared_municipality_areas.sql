-- 0050_shared_municipality_areas.sql
-- VLA-21 — Mapa: obce spoločného obvodu ZŠ Bajkalská (a ostatných obvodov,
-- kde VZN definuje spoločný obvod) zobraziť ako oblasti.
--
-- WHY
--   VZN pools grades 5-9 (or, for some municipalities, all of 1-9) of
--   several neighbouring municipalities into a district's catchment (e.g.
--   ZŠ Bajkalská + Gregorovce/Hubošovce/Uzovce) — today's map shows nothing
--   for these municipalities, so their real distance to the assigned school
--   cannot be visually checked. Descriptive/geographic only — this is NOT a
--   § 44 pass/fail verdict, same boundary VLA-16/17/18 respected for their
--   additive features; it must never feed the RED/S1/S2/S3 semaphore.
--
-- WHAT
--   No new base table — districts.metadata already carries
--   'shared_municipalities' (flat name list) and, as of VLA-21,
--   'shared_municipality_grades' (name -> grade range, e.g.
--   "5. – 9. ročníka", only where the VZN states one explicitly). This view
--   unnests that list, resolves each name to its real polygon in
--   skolske_obvody.municipalities (PSK WFS, geo-psk:admunit_municipalities)
--   via unaccent() — the VZN spelling and WFS spelling disagree on
--   diacritics for at least one real name ("Dulová Ves" vs "Dulova Ves"),
--   confirmed live in the VLA-21 investigation log; exact match silently
--   drops that municipality. Same join pattern as VLA-17's
--   scripts/compute_longest_routes.py::_load_shared_municipality_candidates.
--
--   One row per (district, shared municipality) pair — a municipality
--   shared by two districts' catchments would appear twice, once per owning
--   district, same "no data is missing, drawn once per owner" precedent as
--   the streets pivot (0040_streets_pivot.sql).
--
-- Apply:  python3 scripts/apply_sql.py scripts/sql/0050_shared_municipality_areas.sql

DROP VIEW IF EXISTS public.so_shared_municipality_areas;
CREATE VIEW public.so_shared_municipality_areas AS
SELECT
  d.id AS district_id,
  d.name AS district_name,
  m.id AS municipality_id,
  m.name AS municipality_name,
  (
    SELECT value
    FROM jsonb_each_text(COALESCE(d.metadata->'shared_municipality_grades', '{}'::jsonb))
    WHERE unaccent(key) = unaccent(sm.name)
    LIMIT 1
  ) AS grade_range,
  public.ST_AsGeoJSON(m.geom)::jsonb AS geom_geojson
FROM skolske_obvody.districts d
CROSS JOIN LATERAL jsonb_array_elements_text(
  COALESCE(d.metadata->'shared_municipalities', '[]'::jsonb)
) AS sm(name)
JOIN skolske_obvody.municipalities m
  ON unaccent(m.name) = unaccent(sm.name)
WHERE m.geom IS NOT NULL;

GRANT SELECT ON public.so_shared_municipality_areas TO anon, authenticated, service_role;
