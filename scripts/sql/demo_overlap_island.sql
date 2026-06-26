-- ============================================================================
-- demo_overlap_island.sql — Sprint M-3 demo error scenarios
-- ============================================================================
-- Seeds three classes of § 44 zákona 321 violations the engine is meant
-- to detect, so the client demo can SEE the kinds of problems the system
-- flags:
--
--   1. OVERLAP    (§3 violation) — 2 polygons where 2 districts both claim
--                                  the same addresses
--   2. ISLAND     (§3 violation) — a fragment of a district detached far
--                                  from its main body (segregation hint)
--   3. CAPACITY   (Pa proxy)     — finding text only, no map polygon
--
-- Districts used (all in Prešov):
--   * ZŠ Mirka Nešpora č. 2  = 022b88de-8f54-43fd-9a37-b165102db9f8
--   * ZŠ Šmeralova č. 25     = cddfee4e-fb1d-48c1-bbb5-2626ae415f87
--     (these two share a boundary at distance 0m — natural overlap candidate)
--
-- Idempotency
-- -----------
-- Each row is identified by a `tag` string. We DELETE the previous demo
-- rows by tag, then INSERT fresh — this lets us tweak coordinates / wording
-- and re-apply the seed safely without ON CONFLICT clauses (no unique
-- constraint on geom is sane to construct).
--
-- Real data is NEVER touched: every DELETE is qualified by tag LIKE 'demo:%'
-- AND is_demo = true.
--
-- Apply via scripts/apply_migration_0021.py (same RPC bridge as the
-- migration; the python script runs both files sequentially).
-- ----------------------------------------------------------------------------

-- ============================================================================
-- 0) Clean any previous demo seed
-- ============================================================================
DELETE FROM skolske_obvody.district_overlaps
 WHERE is_demo = true AND tag LIKE 'demo:%';

DELETE FROM skolske_obvody.district_islands
 WHERE is_demo = true AND tag LIKE 'demo:%';

DELETE FROM skolske_obvody.findings
 WHERE is_demo = true AND tag LIKE 'demo:%';

-- ============================================================================
-- 1) OVERLAP scenario — two polygons between Mirka Nešpora č. 2 and
--    Šmeralova č. 25 sitting near their actual shared border.
--    Centroids:
--      Nešpora   = (21.2190, 49.0174)
--      Šmeralova = (21.2354, 49.0134)
--    A point roughly between them at lat ~49.0153 / lon ~21.2271 sits
--    within both districts' rough envelopes — a believable "both VZNs
--    claim this block" demo location.
-- ============================================================================

-- Overlap A — bigger (~50m × 50m, ~0.045 ha at this latitude). One degree
-- of latitude ≈ 111 km, so 50 m ≈ 0.00045 deg; at lat 49° one degree of
-- longitude ≈ 73 km, so 50 m ≈ 0.00068 deg.
INSERT INTO skolske_obvody.district_overlaps
  (district_a_id, district_b_id, overlap_geom, overlap_area_m2,
   severity, tag, is_demo)
SELECT
  '022b88de-8f54-43fd-9a37-b165102db9f8'::uuid,
  'cddfee4e-fb1d-48c1-bbb5-2626ae415f87'::uuid,
  public.ST_GeomFromText(
    'POLYGON((' ||
      '21.22676 49.01505, ' ||
      '21.22744 49.01505, ' ||
      '21.22744 49.01550, ' ||
      '21.22676 49.01550, ' ||
      '21.22676 49.01505' ||
    '))', 4326
  ),
  2500,
  'critical',
  'demo:overlap:nespora-smeralova-a',
  true
WHERE NOT EXISTS (
  SELECT 1 FROM skolske_obvody.district_overlaps
   WHERE tag = 'demo:overlap:nespora-smeralova-a'
);

-- Overlap B — smaller (~30m × 30m, ~0.016 ha) ~100m north of A on the
-- same shared boundary.
INSERT INTO skolske_obvody.district_overlaps
  (district_a_id, district_b_id, overlap_geom, overlap_area_m2,
   severity, tag, is_demo)
SELECT
  '022b88de-8f54-43fd-9a37-b165102db9f8'::uuid,
  'cddfee4e-fb1d-48c1-bbb5-2626ae415f87'::uuid,
  public.ST_GeomFromText(
    'POLYGON((' ||
      '21.22850 49.01640, ' ||
      '21.22891 49.01640, ' ||
      '21.22891 49.01667, ' ||
      '21.22850 49.01667, ' ||
      '21.22850 49.01640' ||
    '))', 4326
  ),
  900,
  'critical',
  'demo:overlap:nespora-smeralova-b',
  true
WHERE NOT EXISTS (
  SELECT 1 FROM skolske_obvody.district_overlaps
   WHERE tag = 'demo:overlap:nespora-smeralova-b'
);

-- ============================================================================
-- 2) ISLAND scenario — a ~100m × 100m fragment ~500m east of the Šmeralova
--    main body. The main district sits in bbox (lon 21.221→21.252,
--    lat 49.002→49.024); we place the demo island at ~(21.260, 49.011)
--    so it is visually clearly detached.
--
--    island_index is allocated to a high number (99) so it does not
--    collide with any real ST_Dump-derived index.
-- ============================================================================
INSERT INTO skolske_obvody.district_islands
  (district_id, island_index, area_m2, geom, streets, house_numbers,
   street_count, house_count, status,
   anomaly_type, severity, tag, is_demo)
SELECT
  'cddfee4e-fb1d-48c1-bbb5-2626ae415f87'::uuid,
  99,
  10000,
  public.ST_GeomFromText(
    'POLYGON((' ||
      '21.25940 49.01050, ' ||
      '21.26075 49.01050, ' ||
      '21.26075 49.01140, ' ||
      '21.25940 49.01140, ' ||
      '21.25940 49.01050' ||
    '))', 4326
  ),
  ARRAY['Demo segregácia']::text[],
  ARRAY['(demo)']::text[],
  1,
  0,
  'unresolved_anomaly',
  'demo:segregation',
  'high',
  'demo:island:smeralova-segregation',
  true
WHERE NOT EXISTS (
  SELECT 1 FROM skolske_obvody.district_islands
   WHERE tag = 'demo:island:smeralova-segregation'
);

-- ============================================================================
-- 3) CAPACITY scenario — pure finding text, no map polygon. Attached to
--    Mirka Nešpora's most recent Pa verdict so the verdict_id NOT NULL
--    constraint is satisfied; the finding itself describes a different,
--    capacity-oriented issue tagged demo:capacity.
-- ============================================================================
INSERT INTO skolske_obvody.findings
  (verdict_id, district_id, municipality_id, condition_code,
   severity, status, evidence_text, engine_version, is_demo, tag)
SELECT
  v.id,
  d.id,
  d.municipality_id,
  'Pa',
  'medium',
  'open',
  'DEMO: Kapacita školy je nižšia ako počet detí v obvode. ' ||
  'Engine: 412 detí v obvode ZŠ Mirka Nešpora č. 2 vs deklarovaná kapacita ' ||
  'budovy 360. Indikuje potrebu re-distribúcie obvodov alebo investície do ' ||
  'kapacity (zdroj EDUZBER + školský register). Demo dáta — reálne čísla po ' ||
  'sprístupnení EDUZBER feedu.',
  'demo-sprint-m-3',
  true,
  'demo:capacity:nespora'
FROM skolske_obvody.districts d
JOIN skolske_obvody.verdicts v
  ON v.district_id = d.id AND v.condition_code = 'Pa'
WHERE d.id = '022b88de-8f54-43fd-9a37-b165102db9f8'
  AND NOT EXISTS (
    SELECT 1 FROM skolske_obvody.findings
     WHERE tag = 'demo:capacity:nespora'
  )
ORDER BY v.computed_at DESC
LIMIT 1;
