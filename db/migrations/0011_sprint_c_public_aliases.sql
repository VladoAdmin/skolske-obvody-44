-- Public alias views for Sprint C (Supabase REST exposure fallback)
-- Idempotent
DROP VIEW IF EXISTS public.so_district_compositions CASCADE;
DROP VIEW IF EXISTS public.so_district_map_features CASCADE;
DROP VIEW IF EXISTS public.so_district_scorecard CASCADE;
DROP VIEW IF EXISTS public.so_municipalities_summary CASCADE;
DROP VIEW IF EXISTS public.so_findings_public CASCADE;
DROP VIEW IF EXISTS public.so_engine_metadata CASCADE;
DROP VIEW IF EXISTS public.so_provenance_allowed_hosts CASCADE;

CREATE VIEW public.so_district_compositions AS SELECT * FROM skolske_obvody.district_compositions;
CREATE VIEW public.so_district_map_features AS SELECT * FROM skolske_obvody.district_map_features;
CREATE VIEW public.so_district_scorecard AS SELECT * FROM skolske_obvody.district_scorecard;
CREATE VIEW public.so_municipalities_summary AS SELECT * FROM skolske_obvody.municipalities_summary;
CREATE VIEW public.so_findings_public AS SELECT * FROM skolske_obvody.findings_public;
CREATE VIEW public.so_engine_metadata AS SELECT * FROM skolske_obvody.engine_metadata;
CREATE VIEW public.so_provenance_allowed_hosts AS SELECT * FROM skolske_obvody.provenance_allowed_hosts;

GRANT SELECT ON
  public.so_district_compositions,
  public.so_district_map_features,
  public.so_district_scorecard,
  public.so_municipalities_summary,
  public.so_findings_public,
  public.so_engine_metadata,
  public.so_provenance_allowed_hosts
TO anon;
