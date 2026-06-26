-- Sprint: register-geocode-confidence.
-- Two additive artifacts built on the authoritative Prešov address register
-- (skolske_obvody.register_adries / view public.so_register_adries):
--
--   1. register_geocode  — cache of REAL Google-geocoded coordinates for a
--      BUDGETED subset of authoritative addresses, keyed on `adresa` so reruns
--      never re-call the paid API. Written by ingest/geocode_register_addresses.py.
--
--   2. district_address_stats — per-district authoritative habitable-address
--      counts + VZN-street coverage (a data-confidence signal). Costs zero API
--      calls. Written by ingest/compute_district_address_stats.py.
--
-- Neither table touches district geometry or the legal Š1–Š3 semafor logic.

-- ---------------------------------------------------------------------------
-- 1. Geocode cache (keyed on adresa — the register's clean address string)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skolske_obvody.register_geocode (
  adresa            TEXT PRIMARY KEY,          -- e.g. "17. novembra 3727/2"
  ulica             TEXT,
  orientacne_cislo  TEXT,
  query_used        TEXT,
  status            TEXT,                       -- Google API status (OK / ZERO_RESULTS / ...)
  lat               DOUBLE PRECISION,
  lon               DOUBLE PRECISION,
  formatted_address TEXT,
  partial_match     BOOLEAN DEFAULT FALSE,
  geocode_tier      TEXT,                       -- 'street_anchor' | 'border_house'
  geom              public.geometry(Point, 4326),
  raw               JSONB,
  geocoded_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS register_geocode_ulica_idx
  ON skolske_obvody.register_geocode (ulica);
CREATE INDEX IF NOT EXISTS register_geocode_geom_gix
  ON skolske_obvody.register_geocode USING GIST (geom);

-- Public read view for the map/UI (PostgREST does not expose skolske_obvody).
CREATE OR REPLACE VIEW public.so_register_geocode AS
SELECT
  adresa, ulica, orientacne_cislo, status, lat, lon,
  formatted_address, partial_match, geocode_tier,
  public.ST_AsGeoJSON(geom)::jsonb AS point_geojson,
  geocoded_at
FROM skolske_obvody.register_geocode
WHERE lat IS NOT NULL AND lon IS NOT NULL;

GRANT SELECT ON public.so_register_geocode TO anon;

-- ---------------------------------------------------------------------------
-- 2. Per-district authoritative address stats (zero API cost)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skolske_obvody.district_address_stats (
  district_id            UUID PRIMARY KEY
                           REFERENCES skolske_obvody.districts (id) ON DELETE CASCADE,
  habitable_addresses    INTEGER NOT NULL DEFAULT 0,  -- authoritative habitable addresses
  register_streets       INTEGER NOT NULL DEFAULT 0,  -- distinct register streets matched to this district's VZN streets
  vzn_streets            INTEGER NOT NULL DEFAULT 0,  -- distinct VZN streets assigned to this district
  vzn_streets_in_register INTEGER NOT NULL DEFAULT 0, -- how many of those VZN streets exist in the register
  street_coverage        DOUBLE PRECISION NOT NULL DEFAULT 0,  -- vzn_streets_in_register / vzn_streets (0..1)
  computed_at            TIMESTAMPTZ DEFAULT now()
);

-- Public read view.
CREATE OR REPLACE VIEW public.so_district_address_stats AS
SELECT
  district_id,
  habitable_addresses,
  register_streets,
  vzn_streets,
  vzn_streets_in_register,
  street_coverage,
  computed_at
FROM skolske_obvody.district_address_stats;

GRANT SELECT ON public.so_district_address_stats TO anon;
