-- Sprint: display-rederived-data (Vlado step 4).
-- Surface the CLEANED authoritative re-derivation (Step 2/3) in the UI without
-- touching district geometry or the legal Š1–Š3 verdict.
--
-- Two additive changes:
--
--   1. district_address_stats gains CLEAN-data columns. The earlier columns were
--      computed against the raw register (register_adries, habitable rows). The
--      new columns are computed against the cleaned canonical set
--      (register_adries_clean — 9402 deduped habitable addresses, the Step-2
--      output). The scorecard now shows the clean/authoritative numbers.
--
--   2. register_mismatches — per-address geometric-consistency signal from the
--      Step-3 analysis: geocoded addresses whose REAL coordinate falls in a
--      different district polygon than their VZN street assigns (72 of 748
--      geocoded points). Stored per address with its VZN district(s) and the
--      polygon district it landed in, plus a read view for the expert map layer.
--      A per-district mismatch COUNT is also denormalised onto
--      district_address_stats for the scorecard figure.
--
-- This is a DATA-QUALITY signal to review, NOT a verdict change. Range-split
-- streets (e.g. Sabinovská) legitimately surface here.

-- ---------------------------------------------------------------------------
-- 1. Clean-data columns on district_address_stats
-- ---------------------------------------------------------------------------
ALTER TABLE skolske_obvody.district_address_stats
  ADD COLUMN IF NOT EXISTS clean_habitable_addresses INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS clean_distinct_streets    INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS clean_street_coverage     DOUBLE PRECISION NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS mismatch_count            INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN skolske_obvody.district_address_stats.clean_habitable_addresses
  IS 'Authoritative habitable addresses on this district''s VZN streets, from the CLEANED canonical set register_adries_clean.';
COMMENT ON COLUMN skolske_obvody.district_address_stats.clean_distinct_streets
  IS 'Distinct cleaned register streets matched to this district''s VZN streets.';
COMMENT ON COLUMN skolske_obvody.district_address_stats.clean_street_coverage
  IS 'Share of this district''s VZN streets that have >=1 cleaned register address (0..1).';
COMMENT ON COLUMN skolske_obvody.district_address_stats.mismatch_count
  IS 'Geocoded addresses assigned to this district by VZN whose real coordinate falls OUTSIDE this district polygon (geometric-consistency signal; not a verdict).';

-- Rebuild the public read view to expose the new columns. DROP first because
-- adding columns to an existing view via CREATE OR REPLACE is rejected
-- ("cannot change name of view column ...").
DROP VIEW IF EXISTS public.so_district_address_stats;
CREATE VIEW public.so_district_address_stats AS
SELECT
  district_id,
  habitable_addresses,
  register_streets,
  vzn_streets,
  vzn_streets_in_register,
  street_coverage,
  clean_habitable_addresses,
  clean_distinct_streets,
  clean_street_coverage,
  mismatch_count,
  computed_at
FROM skolske_obvody.district_address_stats;

GRANT SELECT ON public.so_district_address_stats TO anon;

-- ---------------------------------------------------------------------------
-- 2. Per-address geometric mismatches (Step-3 geometric validation)
-- ---------------------------------------------------------------------------
-- Each row = one geocoded address whose covering polygon disagrees with its
-- VZN-street district. vzn_district_id is the district whose scorecard "owns"
-- the mismatch (the address the VZN assigned here, but whose coordinate fell
-- elsewhere). poly_district_id is where the coordinate actually landed.
CREATE TABLE IF NOT EXISTS skolske_obvody.register_mismatches (
  adresa            TEXT NOT NULL,
  ulica             TEXT,
  vzn_district_id   UUID NOT NULL
                      REFERENCES skolske_obvody.districts (id) ON DELETE CASCADE,
  poly_district_id  UUID
                      REFERENCES skolske_obvody.districts (id) ON DELETE CASCADE,
  lat               DOUBLE PRECISION,
  lon               DOUBLE PRECISION,
  geom              public.geometry(Point, 4326),
  computed_at       TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (adresa, vzn_district_id)
);

CREATE INDEX IF NOT EXISTS register_mismatches_vzn_idx
  ON skolske_obvody.register_mismatches (vzn_district_id);

-- Public read view for the expert map layer (per district, the addresses whose
-- real coordinate falls outside the VZN-assigned district).
CREATE OR REPLACE VIEW public.so_register_mismatches AS
SELECT
  m.adresa,
  m.ulica,
  m.vzn_district_id,
  vd.name  AS vzn_district_name,
  m.poly_district_id,
  pd.name  AS poly_district_name,
  m.lat,
  m.lon,
  public.ST_AsGeoJSON(m.geom)::jsonb AS point_geojson,
  m.computed_at
FROM skolske_obvody.register_mismatches m
LEFT JOIN skolske_obvody.districts vd ON vd.id = m.vzn_district_id
LEFT JOIN skolske_obvody.districts pd ON pd.id = m.poly_district_id
WHERE m.lat IS NOT NULL AND m.lon IS NOT NULL;

GRANT SELECT ON public.so_register_mismatches TO anon;
