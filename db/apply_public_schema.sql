-- ============================================================
-- Public schema tables for Školské obvody § 44
-- Sprint 1: Apply this in Supabase SQL Editor
--
-- Why public schema?
-- The original design used 'skolske_obvody' custom schema, but
-- Supabase PostgREST only exposes schemas listed in project settings
-- (exposed_schemas). Adding a custom schema requires the Supabase
-- Management API (personal access token) or Dashboard access.
-- Until that's configured, all tables live in public with 'so_' prefix.
--
-- To expose 'skolske_obvody' schema later:
--   1. Go to Supabase Dashboard → Settings → API
--   2. Add 'skolske_obvody' to "Exposed schemas"
--   3. Migrate tables: CREATE TABLE skolske_obvody.regions AS SELECT * FROM so_regions;
-- ============================================================

-- Ensure PostGIS is enabled
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- DATASETS (provenance catalogue)
-- ============================================================
CREATE TABLE IF NOT EXISTS so_datasets (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key          TEXT UNIQUE NOT NULL,
  name         TEXT NOT NULL,
  source_url   TEXT,
  description  TEXT,
  completeness SMALLINT CHECK (completeness BETWEEN 1 AND 10),
  validity     SMALLINT CHECK (validity BETWEEN 1 AND 10),
  version      TEXT NOT NULL DEFAULT '1',
  fetched_at   TIMESTAMPTZ,
  source_date  DATE,
  status       TEXT NOT NULL DEFAULT 'active'
                 CHECK (status IN ('pending','staged','validated','active','rejected','superseded')),
  activated_at TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- REGIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS so_regions (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code       TEXT UNIQUE NOT NULL,
  name       TEXT NOT NULL,
  geom       GEOMETRY(MultiPolygon, 4326),
  source_name TEXT,
  source_date DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS so_regions_geom_idx ON so_regions USING GIST(geom);

-- ============================================================
-- MUNICIPALITIES
-- ============================================================
CREATE TABLE IF NOT EXISTS so_municipalities (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id        UUID REFERENCES so_regions(id),
  code             TEXT UNIQUE NOT NULL,
  nuts_code        TEXT,
  name             TEXT NOT NULL,
  geom             GEOMETRY(MultiPolygon, 4326),
  minority_language TEXT,
  source_name      TEXT,
  source_date      DATE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS so_municipalities_geom_idx ON so_municipalities USING GIST(geom);
CREATE INDEX IF NOT EXISTS so_municipalities_nuts_idx ON so_municipalities(nuts_code);

-- ============================================================
-- SCHOOLS
-- ============================================================
CREATE TABLE IF NOT EXISTS so_schools (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  municipality_id   UUID REFERENCES so_municipalities(id),
  municipality_code TEXT,
  eduid             TEXT UNIQUE,
  name              TEXT NOT NULL,
  type              TEXT NOT NULL,
  is_public         BOOLEAN NOT NULL DEFAULT true,
  teaching_language TEXT,
  capacity          INTEGER,
  student_count     INTEGER,
  geom              GEOMETRY(Point, 4326),
  raw_properties    JSONB,
  source_name       TEXT,
  source_date       DATE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS so_schools_geom_idx ON so_schools USING GIST(geom);
CREATE INDEX IF NOT EXISTS so_schools_type_idx ON so_schools(type);

-- ============================================================
-- VZNs (legal instruments)
-- ============================================================
CREATE TABLE IF NOT EXISTS so_vzns (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key               TEXT UNIQUE NOT NULL,
  title             TEXT NOT NULL,
  municipality_name TEXT,
  effective_date    DATE,
  source_url        TEXT,
  raw_text          TEXT,
  source_name       TEXT,
  source_date       DATE,
  fetched_at        TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- DISTRICTS (school catchment areas — core spatial objects)
-- ============================================================
CREATE TABLE IF NOT EXISTS so_districts (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  municipality_id       UUID REFERENCES so_municipalities(id),
  municipality_name     TEXT,
  municipality_nuts     TEXT,
  school_id             UUID REFERENCES so_schools(id),
  vzn_id                UUID REFERENCES so_vzns(id),
  vzn_key               TEXT,
  vzn_article           TEXT,
  district_number       INTEGER,
  name                  TEXT,
  school_name           TEXT,
  school_address        TEXT,
  school_type           TEXT NOT NULL DEFAULT 'ZS',
  teaching_language     TEXT DEFAULT 'SK',
  -- Street list as JSON (for VZN evidence / drill-down)
  streets_json          JSONB,
  street_qualifiers_json JSONB,
  shared_municipalities_json JSONB,
  streets_count         INTEGER,
  geom                  GEOMETRY(MultiPolygon, 4326),
  source_name           TEXT NOT NULL,
  source_date           DATE NOT NULL,
  geometry_quality      SMALLINT CHECK (geometry_quality BETWEEN 1 AND 10),
  geometry_confidence   TEXT CHECK (geometry_confidence IN ('high','medium','low','none')),
  reviewed_by           TEXT,
  reviewed_at           TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS so_districts_geom_idx ON so_districts USING GIST(geom);
CREATE INDEX IF NOT EXISTS so_districts_muni_idx ON so_districts(municipality_nuts);
CREATE INDEX IF NOT EXISTS so_districts_type_idx ON so_districts(school_type, teaching_language);

-- ============================================================
-- ADDRESS POINTS (Register adries MV SR)
-- ============================================================
CREATE TABLE IF NOT EXISTS so_address_points (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  municipality_id  UUID REFERENCES so_municipalities(id),
  municipality_code TEXT,
  street           TEXT,
  house_number     TEXT,
  postal_code      TEXT,
  geom             GEOMETRY(Point, 4326) NOT NULL,
  district_id      UUID REFERENCES so_districts(id),
  source_name      TEXT NOT NULL DEFAULT 'Register adries MV SR',
  source_date      DATE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS so_address_points_geom_idx ON so_address_points USING GIST(geom);
CREATE INDEX IF NOT EXISTS so_address_points_muni_idx ON so_address_points(municipality_code);

-- ============================================================
-- MRK ATLAS 2019
-- ============================================================
CREATE TABLE IF NOT EXISTS so_mrk_atlas (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nuts_code         TEXT UNIQUE,
  municipality_name TEXT,
  district_name     TEXT,
  idn4              INTEGER,
  idn3              INTEGER,
  population_2019   INTEGER,
  roma_share_2019   NUMERIC(5,1),
  roma_count_2019   INTEGER,
  population_2013   INTEGER,
  roma_share_2013   NUMERIC(5,1),
  roma_count_2013   INTEGER,
  geom              GEOMETRY(MultiPolygon, 4326),
  source_name       TEXT,
  source_date       DATE,
  geometry_quality  SMALLINT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS so_mrk_atlas_geom_idx ON so_mrk_atlas USING GIST(geom);

-- ============================================================
-- MRK BUILDINGS (6 PSK municipalities)
-- ============================================================
CREATE TABLE IF NOT EXISTS so_mrk_buildings (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id       TEXT UNIQUE,
  municipality_name TEXT,
  building_name     TEXT,
  building_type     TEXT,
  floor_count       INTEGER,
  condition         TEXT,
  geom              GEOMETRY(Polygon, 4326),
  source_name       TEXT,
  source_date       DATE,
  geometry_quality  SMALLINT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS so_mrk_buildings_geom_idx ON so_mrk_buildings USING GIST(geom);

-- ============================================================
-- TRANSIT STOPS (PAD bus + rail)
-- ============================================================
CREATE TABLE IF NOT EXISTS so_transit_stops (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stop_id           TEXT UNIQUE,
  name              TEXT,
  stop_type         TEXT CHECK (stop_type IN ('bus','rail')),
  district_name     TEXT,
  has_shelter       BOOLEAN,
  geom              GEOMETRY(Point, 4326),
  source_name       TEXT,
  source_date       DATE,
  geometry_quality  SMALLINT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS so_transit_stops_geom_idx ON so_transit_stops USING GIST(geom);

-- ============================================================
-- ROAD NETWORK (PSK categories I/II/III)
-- ============================================================
CREATE TABLE IF NOT EXISTS so_road_network (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  road_id           TEXT UNIQUE,
  category          TEXT CHECK (category IN ('I','II','III')),
  road_number       TEXT,
  manager           TEXT,
  length_m          NUMERIC,
  geom              GEOMETRY(MultiLineString, 4326),
  source_name       TEXT,
  source_date       DATE,
  geometry_quality  SMALLINT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS so_road_network_geom_idx ON so_road_network USING GIST(geom);

-- ============================================================
-- DEMOGRAPHICS (children 0–14 per municipality)
-- ============================================================
CREATE TABLE IF NOT EXISTS so_demographics_children (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nuts_code               TEXT UNIQUE,
  municipality_name       TEXT,
  children_0_14_last      INTEGER,
  children_0_14_2020      INTEGER,
  children_0_14_2019      INTEGER,
  total_population        INTEGER,
  share_pct_last          NUMERIC(5,2),
  source_name             TEXT,
  source_date             DATE,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- TOPOLOGY CHECK RPCs (used by tests/test_topology.py)
-- ============================================================

CREATE OR REPLACE FUNCTION so_check_geometry_validity()
RETURNS TABLE (
  district_number INTEGER,
  school_name     TEXT,
  municipality_name TEXT,
  is_valid        BOOLEAN,
  reason          TEXT
)
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT
    d.district_number,
    d.school_name,
    d.municipality_name,
    ST_IsValid(d.geom) AS is_valid,
    CASE WHEN NOT ST_IsValid(d.geom) THEN ST_IsValidReason(d.geom) ELSE NULL END AS reason
  FROM so_districts d
  WHERE d.geom IS NOT NULL;
$$;

CREATE OR REPLACE FUNCTION so_check_address_coverage(p_municipality TEXT DEFAULT NULL)
RETURNS TABLE (
  address_id      UUID,
  street          TEXT,
  house_number    TEXT,
  municipality_code TEXT,
  district_count  BIGINT,
  failure_type    TEXT,
  districts       TEXT
)
LANGUAGE SQL
SECURITY DEFINER
AS $$
  -- Uncovered addresses
  SELECT
    ap.id,
    ap.street,
    ap.house_number,
    ap.municipality_code,
    0::BIGINT AS district_count,
    'UNCOVERED_ADDRESS'::TEXT AS failure_type,
    NULL::TEXT AS districts
  FROM so_address_points ap
  WHERE (p_municipality IS NULL OR ap.municipality_code IN (
    SELECT DISTINCT municipality_nuts FROM so_districts WHERE municipality_name = p_municipality
  ))
  AND ap.geom IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM so_districts d
    WHERE (d.municipality_nuts = ap.municipality_code OR d.municipality_name = p_municipality)
      AND d.geom IS NOT NULL
      AND ST_Covers(d.geom, ap.geom)
  )
  UNION ALL
  -- Multi-assigned addresses
  SELECT
    ap.id,
    ap.street,
    ap.house_number,
    ap.municipality_code,
    COUNT(d.id) AS district_count,
    'MULTI_ASSIGNED_ADDRESS'::TEXT AS failure_type,
    STRING_AGG(d.school_name, ' | ') AS districts
  FROM so_address_points ap
  JOIN so_districts d
    ON (d.municipality_nuts = ap.municipality_code OR d.municipality_name = p_municipality)
    AND d.geom IS NOT NULL
    AND ap.geom IS NOT NULL
    AND ST_Covers(d.geom, ap.geom)
  WHERE (p_municipality IS NULL OR ap.municipality_code IN (
    SELECT DISTINCT municipality_nuts FROM so_districts WHERE municipality_name = p_municipality
  ))
  GROUP BY ap.id, ap.street, ap.house_number, ap.municipality_code
  HAVING COUNT(d.id) > 1;
$$;

CREATE OR REPLACE FUNCTION so_check_district_overlaps()
RETURNS TABLE (
  district_a      INTEGER,
  district_b      INTEGER,
  municipality_name TEXT,
  school_type     TEXT,
  teaching_language TEXT,
  overlap_area_m2 FLOAT
)
LANGUAGE SQL
SECURITY DEFINER
AS $$
  SELECT
    a.district_number AS district_a,
    b.district_number AS district_b,
    a.municipality_name,
    a.school_type,
    a.teaching_language,
    ST_Area(ST_Intersection(a.geom, b.geom)::geography)::FLOAT AS overlap_area_m2
  FROM so_districts a
  JOIN so_districts b
    ON a.id < b.id
    AND a.municipality_name = b.municipality_name
    AND a.school_type = b.school_type
    AND COALESCE(a.teaching_language, 'SK') = COALESCE(b.teaching_language, 'SK')
    AND a.geom IS NOT NULL
    AND b.geom IS NOT NULL
    AND ST_Intersects(a.geom, b.geom)
    AND ST_Area(ST_Intersection(a.geom, b.geom)::geography) > 1.0;
$$;

-- Grant service role access
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;
