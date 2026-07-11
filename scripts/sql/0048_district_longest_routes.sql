-- 0048_district_longest_routes.sql
-- VLA-17 — Dĺžka cesty: 5 najdlhších peších trás na obvod + prímestská doprava.
--
-- WHY
--   Replaces the superseded threshold-based ("prah 2/4 km PASS-FAIL")
--   approach — this is explicitly a comparison/overview, NOT a legal
--   verdict. § 44 ods. 8 sets no numeric distance limit, so this table
--   carries no threshold/pass-fail column and must never feed the § 44
--   semaphore (S1-S3 / Pa-Pf / JAZYK).
--
-- WHAT
--   Precomputed (not live-routed on page load, per Linear spec) top-5
--   longest real walking routes per district, from Google Maps Directions
--   API — never a straight-line substitute (ZERO_RESULTS / API errors drop
--   the candidate, they are not guessed). For districts with shared
--   municipalities (grades 5-9 catchment beyond the seat municipality —
--   districts.metadata->'shared_municipalities'), any top-5 route whose
--   origin is one of those municipalities additionally carries a transit
--   (prímestská doprava) alternative.
--
--   Candidate origins:
--     'street_geocode'      — skolske_obvody.street_geocodes (VZN street,
--                              real Google-geocoded point, Prešov only)
--     'shared_municipality'  — skolske_obvody.municipalities polygon
--                              centroid (real WFS geometry) for a
--                              municipality named in the district's
--                              shared_municipalities metadata
--
-- Populated by: scripts/compute_longest_routes.py (Python, calls Google
-- Maps Directions API directly — mirrors ingest/google_geocode_streets.py
-- conventions, not the services/routing-google/client.ts TS scaffold,
-- which is for future Next.js-side use and has no Python equivalent).
--
-- Apply:  python3 scripts/apply_sql.py scripts/sql/0048_district_longest_routes.sql
-- Then:   python3 scripts/compute_longest_routes.py

CREATE TABLE IF NOT EXISTS skolske_obvody.district_longest_routes (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  district_id         UUID NOT NULL REFERENCES skolske_obvody.districts(id),
  rank                SMALLINT NOT NULL CHECK (rank BETWEEN 1 AND 5),
  origin_kind         TEXT NOT NULL CHECK (origin_kind IN ('street_geocode', 'shared_municipality')),
  origin_label        TEXT NOT NULL,   -- street name, or municipality name for shared-municipality origins
  origin_geom         public.geometry(Point, 4326) NOT NULL,
  distance_m          INTEGER NOT NULL,
  duration_s          INTEGER NOT NULL,
  route_geom          public.geometry(LineString, 4326) NOT NULL,  -- decoded Google walking polyline
  -- Transit alternative — only populated for shared-municipality origins that made the top 5.
  transit_status      TEXT CHECK (transit_status IN ('ok', 'low_data', 'unavailable')),
  transit_distance_m  INTEGER,
  transit_duration_s  INTEGER,
  transit_geom        public.geometry(LineString, 4326),
  transit_line        TEXT,   -- e.g. "Autobus 22"; NULL if not extracted
  provenance          JSONB NOT NULL,  -- {source, google_status, query_used, ...}
  computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (district_id, rank)
);

CREATE INDEX IF NOT EXISTS district_longest_routes_district_idx
  ON skolske_obvody.district_longest_routes (district_id);

-- Public read view (PostgREST does not expose the skolske_obvody schema).
DROP VIEW IF EXISTS public.so_district_longest_routes;
CREATE VIEW public.so_district_longest_routes AS
SELECT
  r.id,
  r.district_id,
  r.rank,
  r.origin_kind,
  r.origin_label,
  public.ST_AsGeoJSON(r.origin_geom)::jsonb AS origin_geojson,
  r.distance_m,
  r.duration_s,
  public.ST_AsGeoJSON(r.route_geom)::jsonb AS route_geojson,
  r.transit_status,
  r.transit_distance_m,
  r.transit_duration_s,
  public.ST_AsGeoJSON(r.transit_geom)::jsonb AS transit_geojson,
  r.transit_line,
  r.computed_at
FROM skolske_obvody.district_longest_routes r;

GRANT SELECT ON public.so_district_longest_routes TO anon, authenticated, service_role;
