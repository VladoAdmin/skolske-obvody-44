-- 0042_house_points_demo_flag.sql
-- Step 2 Sprint 3 — GUI integration.
--
-- WHY
--   so_house_points / so_house_dots (the map's per-address layers) do not
--   expose house_geocodes.is_demo, so the map cannot visually distinguish the
--   0041 demo address-overlap seed (Kúpeľná č. 2 / Sibírska č. 42) from real
--   Register-adries data. Sprint 3 needs the map to show "selected demo
--   evidence points... driven by engine/data outputs (no UI hardcodes)" — the
--   GUI must read is_demo from data, not string-match the demo street name.
--
-- WHAT
--   Re-create both views (CREATE OR REPLACE — same columns as the live
--   definitions, plus is_demo) so existing selects keep working unchanged.
--
-- Apply: python3 scripts/apply_sql.py scripts/sql/0042_house_points_demo_flag.sql

CREATE OR REPLACE VIEW public.so_house_dots AS
SELECT
  h.district_id,
  h.street,
  h.house_number,
  h.lat,
  h.lon,
  h.is_demo
FROM skolske_obvody.house_geocodes h
JOIN skolske_obvody.districts d ON d.id = h.district_id
JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
WHERE m.slug = 'presov'
  AND h.lat IS NOT NULL
  AND h.lon IS NOT NULL
  AND COALESCE(h.valid, TRUE) = TRUE;

GRANT SELECT ON public.so_house_dots TO anon, authenticated, service_role;

CREATE OR REPLACE VIEW public.so_house_points AS
WITH presov AS (SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov')
SELECT
  hg.district_id,
  hg.street,
  hg.house_number,
  hg.lat,
  hg.lon,
  hg.status,
  hg.partial_match,
  hg.formatted_address,
  public.ST_AsGeoJSON(hg.geom)::jsonb AS point_geojson,
  hg.valid,
  hg.validation_reason,
  hg.is_demo
FROM skolske_obvody.house_geocodes hg
JOIN skolske_obvody.districts d ON d.id = hg.district_id
WHERE d.municipality_id = (SELECT id FROM presov)
  AND hg.lat IS NOT NULL;

GRANT SELECT ON public.so_house_points TO anon, authenticated, service_role;
