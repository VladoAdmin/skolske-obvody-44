-- Sprint: color school pins by founder (public Prešov vs private)
-- Adds is_public to public.so_school_markers so the map can colour-code pins.
-- Idempotent: CREATE OR REPLACE VIEW. The new column is appended LAST because
-- CREATE OR REPLACE VIEW in Postgres only allows adding columns at the end
-- (it cannot reorder/insert before existing columns).

CREATE OR REPLACE VIEW public.so_school_markers AS
SELECT
  s.id,
  s.name,
  s.type AS kind,
  public.ST_AsGeoJSON(s.geom)::jsonb AS geom_geojson,
  s.is_public
FROM skolske_obvody.schools s
WHERE s.municipality_id = (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov'
)
AND s.geom IS NOT NULL;

GRANT SELECT ON public.so_school_markers TO anon;
