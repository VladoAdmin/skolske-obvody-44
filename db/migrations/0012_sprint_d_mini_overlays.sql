-- Sprint D-mini overlay views: school markers, MRK polygons, findings panel
-- Idempotent DROP + CREATE

DROP VIEW IF EXISTS public.so_school_markers CASCADE;
DROP VIEW IF EXISTS public.so_mrk_overlays CASCADE;
DROP VIEW IF EXISTS public.so_findings_panel CASCADE;

-- 1. All schools in Prešov municipality (not just those linked to a district)
CREATE VIEW public.so_school_markers AS
SELECT
  s.id,
  s.name,
  s.type AS kind,
  public.ST_AsGeoJSON(s.geom)::jsonb AS geom_geojson
FROM skolske_obvody.schools s
WHERE s.municipality_id = (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov'
)
AND s.geom IS NOT NULL;

-- 2. MRK polygons intersecting any Prešov district
CREATE VIEW public.so_mrk_overlays AS
SELECT
  m.id,
  m.obec_name AS name,
  m.category AS severity_class,
  public.ST_AsGeoJSON(m.geom)::jsonb AS geom_geojson
FROM skolske_obvody.mrk_atlas m
WHERE public.ST_Intersects(
  m.geom,
  (
    SELECT public.ST_Union(d.geom)
    FROM skolske_obvody.districts d
    WHERE d.municipality_id = (
      SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov'
    )
  )
);

-- 3. Findings panel -- critical/high/medium only, with district centroid for flyTo
CREATE VIEW public.so_findings_panel AS
SELECT
  fp.finding_id,
  fp.district_id,
  fp.district_name,
  fp.municipality_id,
  fp.municipality_name,
  fp.condition_code,
  fp.condition_label_sk,
  fp.severity,
  fp.severity_rank,
  fp.status,
  fp.evidence_public_text,
  fp.provenance_source,
  fp.created_at,
  public.ST_X(public.ST_Centroid(d.geom)) AS district_geom_centroid_lon,
  public.ST_Y(public.ST_Centroid(d.geom)) AS district_geom_centroid_lat
FROM skolske_obvody.findings_public fp
JOIN skolske_obvody.districts d ON d.id = fp.district_id
WHERE fp.severity IN ('critical', 'high', 'medium');

-- Permissions
GRANT SELECT ON public.so_school_markers, public.so_mrk_overlays, public.so_findings_panel TO anon;
