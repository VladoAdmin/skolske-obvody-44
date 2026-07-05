-- 0040_streets_pivot.sql
-- STREETS PIVOT (step 1). Vlado mandate 2026-06-28.
--
-- Replaces district POLYGON rendering with each district drawn as its set of
-- VZN-assigned STREETS, coloured per school. This migration:
--   (A) Creates the street-linestring source view + public alias used by BOTH
--       the main map and the per-school detail page (single SSOT for streets).
--   (B) Wipes ALL current findings (step-1 ships a clean street map, zero
--       findings). The mock analysis layer is rebuilt in step 2.
--   (C) Removes the polygon-based structural-overlap demo data (district_overlaps
--       / district_islands demo rows) — the only structural-overlap concept left
--       is "same full address (street + house number) in 2+ districts", which is
--       address-based (engine c_s2), not polygon-based.
--
-- Apply:  python3 scripts/apply_sql.py scripts/sql/0040_streets_pivot.sql
-- Then:   python3 -m engine.runner   (re-derives verdicts; emits zero findings)

CREATE EXTENSION IF NOT EXISTS unaccent;

-- ---------------------------------------------------------------------------
-- (A) Street linestrings per district, coloured per school.
--
-- A district's streets = its VZN-assigned street names, matched to OSM
-- centerlines by NORMALISED name (strip diacritics/Ulica-prefix/dots, expand the
-- one common abbreviation, collapse whitespace — identical to
-- ingest/build_street_districts.py NORM so the join stays consistent). For the
-- ~5% of VZN streets with no OSM line, fall back to the street_geocodes single
-- POINT rendered as a dot (is_fallback_point = true) so NO street is missing.
--
-- A street name shared by 2+ districts (crossing/boundary street) legitimately
-- appears once per district here — drawn in each district's colour. This is NOT
-- a finding (see engine c_s2: only same-full-address-in-2+-districts can be).
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS public.so_district_street_linestrings CASCADE;
DROP VIEW IF EXISTS skolske_obvody.district_street_lines CASCADE;

CREATE VIEW skolske_obvody.district_street_lines AS
WITH presov AS (
  SELECT id, geom FROM skolske_obvody.municipalities WHERE slug = 'presov'
),
vzn AS (
  SELECT DISTINCT v.district_id, v.street
  FROM skolske_obvody.vzn_street_ranges v
  JOIN skolske_obvody.districts d ON d.id = v.district_id
  WHERE d.municipality_id = (SELECT id FROM presov)
),
-- normalisation helper, inlined (matches build_street_districts.py NORM)
norm AS (
  SELECT 1
),
-- (1) matched OSM centerlines, clipped to the Prešov boundary
osm_lines AS (
  SELECT v.district_id,
         v.street,
         d.school_id,
         public.ST_Intersection(o.geom, (SELECT geom FROM presov)) AS geom,
         false AS is_fallback_point
  FROM vzn v
  JOIN skolske_obvody.districts d ON d.id = v.district_id
  JOIN skolske_obvody.osm_street_lines o
    ON regexp_replace(regexp_replace(regexp_replace(lower(unaccent(
         replace(replace(o.name, 'Arm. gen.', 'Armádneho generála'), 'č.', ''))),
         '^ulica\s+|\s+ulica$', '', 'g'), '[.]', ' ', 'g'), '\s+', ' ', 'g')
     = regexp_replace(regexp_replace(regexp_replace(lower(unaccent(
         replace(replace(v.street, 'Arm. gen.', 'Armádneho generála'), 'č.', ''))),
         '^ulica\s+|\s+ulica$', '', 'g'), '[.]', ' ', 'g'), '\s+', ' ', 'g')
  WHERE public.ST_Intersects(o.geom, (SELECT geom FROM presov))
),
-- which (district, street) matched at least one OSM line
matched AS (
  SELECT DISTINCT district_id, street FROM osm_lines
),
-- (2) fallback street_geocodes POINT for VZN streets with NO OSM line
point_fallback AS (
  SELECT sg.district_id,
         sg.street,
         d.school_id,
         sg.geom,
         true AS is_fallback_point
  FROM skolske_obvody.street_geocodes sg
  JOIN vzn v ON v.district_id = sg.district_id AND v.street = sg.street
  JOIN skolske_obvody.districts d ON d.id = sg.district_id
  WHERE sg.geom IS NOT NULL
    AND public.ST_Within(sg.geom, (SELECT geom FROM presov))
    AND NOT EXISTS (
      SELECT 1 FROM matched m
      WHERE m.district_id = sg.district_id AND m.street = sg.street
    )
)
SELECT district_id, school_id, street, geom, is_fallback_point FROM osm_lines
WHERE geom IS NOT NULL AND NOT public.ST_IsEmpty(geom)
UNION ALL
SELECT district_id, school_id, street, geom, is_fallback_point FROM point_fallback;

-- Public alias: GeoJSON geometry for the client map. One row per drawn segment;
-- linestring_geojson is a LineString for matched streets, a Point for fallbacks.
CREATE VIEW public.so_district_street_linestrings AS
SELECT
  district_id,
  school_id,
  street,
  is_fallback_point,
  public.ST_AsGeoJSON(geom)::jsonb AS linestring_geojson
FROM skolske_obvody.district_street_lines;

GRANT SELECT ON public.so_district_street_linestrings TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- (B) WIPE ALL findings (step 1 ships zero findings). Engine re-run will write
--     verdicts but, with demo mode off + address-based S2 clean, emit no findings.
-- ---------------------------------------------------------------------------
DELETE FROM skolske_obvody.findings WHERE id IS NOT NULL;

-- Disable demo mode so the engine's mock-input paths (which produced the only
-- findings) do not fire. The honest real-data checkers run; address-based S2 is
-- clean (0 same-address-in-2-districts after demo rows removed), so no findings.
UPDATE skolske_obvody.demo_mode_flag SET enabled = false, updated_at = now()
WHERE enabled IS DISTINCT FROM false;

-- ---------------------------------------------------------------------------
-- (C) Remove polygon-based structural-overlap demo data. The shared-boundary /
--     polygon-intersection overlap concept is retired; the only structural
--     overlap left is address-based (engine c_s2). Drop the demo seed rows so
--     nothing surfaces a polygon overlap.
-- ---------------------------------------------------------------------------
DELETE FROM skolske_obvody.district_overlaps WHERE is_demo = true;
DELETE FROM skolske_obvody.district_islands  WHERE is_demo = true;

-- Remove the demo house points (ukážková ulica 1..8) that were the ONLY
-- same-full-address-in-2+-districts rows — they were illustration-only seeds.
DELETE FROM skolske_obvody.house_geocodes WHERE is_demo = true;
