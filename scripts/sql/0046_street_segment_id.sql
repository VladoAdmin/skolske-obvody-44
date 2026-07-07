-- VLA-10: stable, unique ordering column for so_district_street_linestrings.
--
-- lib/supabase/fetch-all.ts pages this view (2974 rows > PostgREST's 1000-row
-- cap) via .range() with no ORDER BY. Without one, Postgres does not guarantee
-- row order is stable across the successive queries a paged fetch issues, so
-- concurrent writes or a changed query plan can return a row twice or skip it.
--
-- (district_id, school_id, street, is_fallback_point) is NOT a usable sort key
-- on its own: 2863 of 2974 rows share that tuple with at least one sibling
-- segment (a street is drawn as many OSM line segments), so ordering by it
-- alone still leaves large tied groups. The underlying rows have real ids
-- (osm_street_lines.id bigint, street_geocodes.id uuid) that are just never
-- surfaced — but a bare source id is still not unique in the OUTPUT: a
-- boundary street legitimately joins the same OSM line to 2+ districts (one
-- row drawn per district, by design — see comment above), so o.id repeats
-- once per district it's assigned to. Pairing the source id with district_id
-- makes it unique per output row.
CREATE OR REPLACE VIEW skolske_obvody.district_street_lines AS
WITH presov AS (
  SELECT id, geom FROM skolske_obvody.municipalities WHERE slug = 'presov'
),
vzn AS (
  SELECT DISTINCT v.district_id, v.street
  FROM skolske_obvody.vzn_street_ranges v
  JOIN skolske_obvody.districts d ON d.id = v.district_id
  WHERE d.municipality_id = (SELECT id FROM presov)
),
-- (1) matched OSM centerlines, clipped to the Prešov boundary
osm_lines AS (
  SELECT v.district_id,
         v.street,
         d.school_id,
         public.ST_Intersection(o.geom, (SELECT geom FROM presov)) AS geom,
         false AS is_fallback_point,
         'osm:' || o.id::text || ':' || v.district_id::text AS segment_id
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
         true AS is_fallback_point,
         'geo:' || sg.id::text || ':' || sg.district_id::text AS segment_id
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
SELECT district_id, school_id, street, geom, is_fallback_point, segment_id FROM osm_lines
WHERE geom IS NOT NULL AND NOT public.ST_IsEmpty(geom)
UNION ALL
SELECT district_id, school_id, street, geom, is_fallback_point, segment_id FROM point_fallback;

-- Public alias: unchanged shape plus segment_id for stable pagination order.
CREATE OR REPLACE VIEW public.so_district_street_linestrings AS
SELECT
  district_id,
  school_id,
  street,
  is_fallback_point,
  public.ST_AsGeoJSON(geom)::jsonb AS linestring_geojson,
  segment_id
FROM skolske_obvody.district_street_lines;
