-- 0038_mrk_localities_view.sql
-- Item 14 — "MRK lokality" map layer was lighting up the WHOLE city of Prešov.
--
-- Root cause: the layer rendered so_mrk_overlays, which selects the
-- OBEC-LEVEL polygon from skolske_obvody.mrk_atlas (Atlas MRK 2019 keyed by
-- obec). For Prešov the whole obec is one polygon tagged "large" → the entire
-- city reads as one big MRK hatch. That polygon is correct context for the
-- engine's P-e checker, but wrong for a "lokality" map layer.
--
-- Fix: a locality-level view over skolske_obvody.mrk_buildings (per-building
-- POINT geometries). Only buildings that actually fall inside the Prešov city
-- districts are exposed, so the map shows the real locality points — NOT the
-- whole-city polygon. For Prešov this is a sparse set (~10 points); the map
-- renders those points (or nothing if empty) rather than the obec polygon.
--
-- Idempotent: CREATE OR REPLACE VIEW.

CREATE OR REPLACE VIEW public.so_mrk_localities AS
SELECT
    b.id,
    b.obec                                     AS obec_name,
    public.ST_AsGeoJSON(b.geom)::jsonb         AS geom_geojson
FROM skolske_obvody.mrk_buildings b
WHERE EXISTS (
    SELECT 1
    FROM skolske_obvody.districts d
    WHERE d.municipality_id = (
        SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov'
    )
      AND public.ST_Intersects(b.geom, d.geom)
);

GRANT SELECT ON public.so_mrk_localities TO anon, authenticated;
