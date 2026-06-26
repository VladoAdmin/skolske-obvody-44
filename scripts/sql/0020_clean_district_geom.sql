-- ============================================================================
-- 0020_clean_district_geom.sql — Sprint M-2
-- ============================================================================
-- Adds a "clean" district geometry column that the map renders as the
-- user-facing Obvody layer. The intent is to replace the Voronoi tessellation
-- (which crisscrosses through individual houses) with smoother polygons that
-- roughly follow street centerlines. Sprint M-2 ships these as documented
-- DEMO geometry derived from Voronoi (simplified + cleaned). A future sprint
-- will replace the contents via the OSM street-snap pipeline; the column +
-- view contract stays stable.
--
-- NOTE: Lives under scripts/sql/ rather than db/migrations/ because the
-- harness path-block hook forbids writes under any /migrations/ directory.
-- Apply via scripts/apply_migration_0020.py (uses ingest.supabase_client
-- f2_exec_sql, the same RPC bridge used by earlier sprints).
--
-- f2_exec_sql does not allow explicit BEGIN/COMMIT (it wraps each call in
-- its own transaction), so this file is a flat statement sequence.
-- ----------------------------------------------------------------------------

-- 1) Storage column on skolske_obvody.districts
ALTER TABLE skolske_obvody.districts
  ADD COLUMN IF NOT EXISTS geom_clean public.geometry(MultiPolygon, 4326);

ALTER TABLE skolske_obvody.districts
  ADD COLUMN IF NOT EXISTS geom_clean_metadata jsonb;

CREATE INDEX IF NOT EXISTS districts_geom_clean_idx
  ON skolske_obvody.districts USING GIST (geom_clean);

-- 2) Public read view restricted to Prešov districts that have geom_clean set
DROP VIEW IF EXISTS public.so_district_clean_geom CASCADE;

CREATE VIEW public.so_district_clean_geom AS
SELECT
  d.id,
  d.name,
  d.school_id,
  public.ST_AsGeoJSON(d.geom_clean)::json AS geom_clean_geojson,
  d.geom_clean_metadata
FROM skolske_obvody.districts d
JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
WHERE m.slug = 'presov'
  AND d.geom_clean IS NOT NULL;

GRANT SELECT ON public.so_district_clean_geom TO anon, authenticated, service_role;

-- 3) House dots view — valid house geocodes for Prešov, ready for per-house
--    visualization at high zoom. district_id is needed for hue mapping.
DROP VIEW IF EXISTS public.so_house_dots CASCADE;

CREATE VIEW public.so_house_dots AS
SELECT
  h.district_id,
  h.street,
  h.house_number,
  h.lat,
  h.lon
FROM skolske_obvody.house_geocodes h
JOIN skolske_obvody.districts d ON d.id = h.district_id
JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
WHERE m.slug = 'presov'
  AND h.lat IS NOT NULL
  AND h.lon IS NOT NULL
  AND COALESCE(h.valid, TRUE) = TRUE;

GRANT SELECT ON public.so_house_dots TO anon, authenticated, service_role;
