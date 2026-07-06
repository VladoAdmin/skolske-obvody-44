-- 0043_street_coverage_gaps.sql
-- VLA-14 — Map coverage gaps: classify VZN gap vs data gap.
--
-- WHY
--   The streets-pivot map draws ONLY VZN-assigned streets, so every street
--   with no VZN assignment renders as a "hole". Owner mandate: every hole must
--   be explicitly classified and shown as exactly one of:
--     * vzn_gap  — the street IS in the authoritative Register adries
--                  (register_adries_clean: habitable, not withdrawn) but NO VZN
--                  assigns it to any school district. A real § 44 ods. 1
--                  structural finding (Š1 family: every address must belong to
--                  a district).
--     * data_gap — the name exists only in map data (OSM) and cannot be
--                  anchored to the register (name mismatch, passages,
--                  courtyards, non-address spaces). "Neurčené — dátová
--                  medzera"; NEVER presented as a violation.
--
-- WHAT
--   Schema only: the classified rows are WRITTEN BY THE ENGINE
--   (engine/coverage_gaps.py, called from engine/runner.py) so the engine
--   stays the single source of truth — the GUI reads the view below and never
--   classifies anything itself.
--
-- Apply:  python3 scripts/apply_sql.py scripts/sql/0043_street_coverage_gaps.sql
-- Then:   python3 -m engine.coverage_gaps   (or a full engine.runner run)

CREATE TABLE IF NOT EXISTS skolske_obvody.street_coverage_gaps (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  municipality_id        UUID NOT NULL,
  street                 TEXT NOT NULL,   -- display spelling (register for vzn_gap, OSM for data_gap)
  street_norm            TEXT NOT NULL,   -- shared normalisation (join/dedupe key)
  category               TEXT NOT NULL CHECK (category IN ('vzn_gap', 'data_gap')),
  in_register            BOOLEAN NOT NULL,
  in_vzn                 BOOLEAN NOT NULL DEFAULT FALSE,
  register_address_count INTEGER NOT NULL DEFAULT 0,  -- habitable, non-withdrawn addresses
  has_osm_line           BOOLEAN NOT NULL,
  reason_sk              TEXT NOT NULL,   -- popup evidence text (Slovak)
  provenance             JSONB,           -- sources + counts, engine conventions
  geom                   public.geometry(Geometry, 4326),  -- OSM lines clipped to the city (NULL if none)
  is_demo                BOOLEAN NOT NULL DEFAULT FALSE,   -- demo/mock rows flagged, never a violation
  engine_version         TEXT NOT NULL,
  computed_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (municipality_id, category, street_norm)
);

CREATE INDEX IF NOT EXISTS street_coverage_gaps_mun_cat_idx
  ON skolske_obvody.street_coverage_gaps (municipality_id, category);

-- Public read view (PostgREST does not expose the skolske_obvody schema).
DROP VIEW IF EXISTS public.so_street_coverage_gaps;
CREATE VIEW public.so_street_coverage_gaps AS
SELECT
  g.street,
  g.category,
  g.in_register,
  g.in_vzn,
  g.register_address_count,
  g.has_osm_line,
  g.reason_sk,
  g.is_demo,
  public.ST_AsGeoJSON(g.geom)::jsonb AS geom_geojson
FROM skolske_obvody.street_coverage_gaps g;

GRANT SELECT ON public.so_street_coverage_gaps TO anon, authenticated, service_role;
