-- ============================================================
-- Sprint C: Read-only views, PII sanitization, provenance allowlist
-- Migration: 0010_sprint_c_read_views.sql
-- Idempotent: DROP ... IF EXISTS CASCADE before CREATE
-- ============================================================

-- ----- Idempotent teardown -----
DROP VIEW IF EXISTS skolske_obvody.district_compositions CASCADE;
DROP VIEW IF EXISTS skolske_obvody.district_map_features CASCADE;
DROP VIEW IF EXISTS skolske_obvody.district_scorecard CASCADE;
DROP VIEW IF EXISTS skolske_obvody.municipalities_summary CASCADE;
DROP VIEW IF EXISTS skolske_obvody.findings_public CASCADE;
DROP VIEW IF EXISTS skolske_obvody.engine_metadata CASCADE;
DROP VIEW IF EXISTS skolske_obvody.provenance_allowed_hosts CASCADE;
DROP FUNCTION IF EXISTS skolske_obvody.host_in_allowlist(text);
DROP FUNCTION IF EXISTS skolske_obvody.sanitize_evidence(text, int);

-- ----- §2.0 slug column -----
ALTER TABLE skolske_obvody.municipalities ADD COLUMN IF NOT EXISTS slug TEXT;

UPDATE skolske_obvody.municipalities
SET slug = 'presov'
WHERE slug IS NULL
  AND (lower(name) = 'prešov' OR lower(name) = 'presov' OR lower(name) = 'mesto prešov');

UPDATE skolske_obvody.municipalities
SET slug = lower(regexp_replace(translate(name, 'áäčďéíĺľňóôŕšťúýž', 'aacdeillnoorstuyz'), '[^a-z0-9]+', '-', 'g'))
WHERE slug IS NULL AND name IS NOT NULL;

CREATE INDEX IF NOT EXISTS municipalities_slug_idx ON skolske_obvody.municipalities(slug);

-- ----- §2.1 host_in_allowlist function -----
CREATE OR REPLACE FUNCTION skolske_obvody.host_in_allowlist(url text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $$
  WITH
    norm AS (
      SELECT
        CASE WHEN url IS NULL THEN NULL
             ELSE lower(regexp_replace(url, '^[Hh][Tt][Tt][Pp][Ss]?://([^/:]+).*$', '\1'))
        END AS host
    ),
    allowlist(allowed) AS (VALUES
      ('slov-lex.sk'), ('cvti.sk'), ('osm.org'), ('openstreetmap.org'),
      ('geoportal.gov.sk'), ('presov.sk'), ('gov.sk'), ('statistics.sk'),
      ('atlasromskychkomunit.sk'), ('minedu.sk'), ('mzv.sk')
    )
  SELECT EXISTS (
    SELECT 1
    FROM norm, allowlist
    WHERE norm.host IS NOT NULL
      AND (norm.host = allowlist.allowed OR norm.host LIKE ('%.' || allowlist.allowed))
  );
$$;

-- ----- §2.2 sanitize_evidence function -----
CREATE OR REPLACE FUNCTION skolske_obvody.sanitize_evidence(t text, max_len int)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT LEFT(
    regexp_replace(
      regexp_replace(
        regexp_replace(
          coalesce(t, ''),
          '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[email]', 'g'
        ),
        '\+?\d{2,4}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2,3}', '[tel]', 'g'
      ),
      '\d{6}\s*/\s*\d{3,4}', '[rč]', 'g'
    ),
    max_len
  );
$$;

-- ----- §2.3 district_compositions VIEW -----
-- Port of engine/compose.py compose_color() — 1:1 rule mapping:
--   RED    = any S1/S2/S3 value = 'FAIL'
--   ORANGE = S1/S2/S3 has INCOMPLETE OR Pa/Pb/Pc/Pd has RISK or INSUFFICIENT_DATA (non-illustrative only)
--   GREEN  = all S1-S3 PASS, no non-illustrative indicator risk
--   NONE   = no verdicts at all (engine hasn't run)
-- Pe/Pf: analytical signals only, NEVER degrade semafor (per compose.py SIGNAL_CONDITIONS)

CREATE OR REPLACE VIEW skolske_obvody.district_compositions AS
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov' LIMIT 1
),
latest AS (
  SELECT DISTINCT ON (v.district_id, v.condition_code)
    v.district_id,
    v.condition_code,
    v.value,
    v.is_illustrative,
    v.engine_version,
    v.methodology_version,
    v.computed_at
  FROM skolske_obvody.verdicts v
  JOIN skolske_obvody.districts d ON d.id = v.district_id
  WHERE d.municipality_id = (SELECT id FROM presov)
  ORDER BY v.district_id, v.condition_code, v.computed_at DESC
),
legal AS (
  SELECT district_id,
    bool_or(value = 'FAIL') AS any_fail,
    bool_or(value = 'INCOMPLETE') AS any_incomplete
  FROM latest
  WHERE condition_code IN ('S1', 'S2', 'S3')
  GROUP BY district_id
),
indicators AS (
  SELECT district_id,
    bool_or(value IN ('RISK', 'INSUFFICIENT_DATA')) AS any_indicator_risk
  FROM latest
  WHERE condition_code IN ('Pa', 'Pb', 'Pc', 'Pd')
    AND NOT is_illustrative
  GROUP BY district_id
),
meta AS (
  SELECT
    district_id,
    MAX(engine_version) AS engine_version,
    MAX(methodology_version) AS methodology_version,
    MAX(computed_at) AS computed_at
  FROM latest
  GROUP BY district_id
)
SELECT
  d.id AS district_id,
  CASE
    WHEN l.district_id IS NULL THEN 'NONE'
    WHEN l.any_fail THEN 'RED'
    WHEN l.any_incomplete OR COALESCE(i.any_indicator_risk, false) THEN 'ORANGE'
    ELSE 'GREEN'
  END AS composition_color,
  CASE
    WHEN l.district_id IS NULL THEN 'Bez verdiktov'
    WHEN l.any_fail THEN 'FAIL v zákonných podmienkach'
    WHEN l.any_incomplete AND COALESCE(i.any_indicator_risk, false) THEN 'NEÚPLNÉ zákonné podmienky; Rizikové indikátory'
    WHEN l.any_incomplete THEN 'NEÚPLNÉ zákonné podmienky'
    WHEN COALESCE(i.any_indicator_risk, false) THEN 'Rizikové indikátory'
    ELSE 'Š1–Š3 PASS, žiadne rizikové indikátory'
  END AS composition_reason,
  jsonb_build_object(
    'legal_fail', COALESCE(l.any_fail, false),
    'legal_incomplete', COALESCE(l.any_incomplete, false),
    'indicator_risk', COALESCE(i.any_indicator_risk, false)
  ) AS composition_details,
  m.engine_version,
  m.methodology_version,
  m.computed_at
FROM skolske_obvody.districts d
LEFT JOIN legal l ON l.district_id = d.id
LEFT JOIN indicators i ON i.district_id = d.id
LEFT JOIN meta m ON m.district_id = d.id
WHERE d.municipality_id = (SELECT id FROM presov);

-- ----- §2.4 district_map_features VIEW -----
CREATE OR REPLACE VIEW skolske_obvody.district_map_features AS
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov' LIMIT 1
)
SELECT
  d.id,
  d.name,
  d.municipality_id,
  d.school_id,
  d.geometry_confidence,
  COALESCE(dc.composition_color, 'NONE') AS composition_color,
  dc.composition_reason,
  CASE
    WHEN d.geom IS NOT NULL
    THEN ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom, 0.0001))::jsonb
    ELSE NULL
  END AS geom_geojson,
  CASE
    WHEN s.geom IS NOT NULL
    THEN ST_AsGeoJSON(s.geom)::jsonb
    ELSE NULL
  END AS school_geom_geojson,
  s.name AS school_name
FROM skolske_obvody.districts d
LEFT JOIN skolske_obvody.schools s ON s.id = d.school_id
LEFT JOIN skolske_obvody.district_compositions dc ON dc.district_id = d.id
WHERE d.municipality_id = (SELECT id FROM presov);

-- ----- §2.4 district_scorecard VIEW -----
CREATE OR REPLACE VIEW skolske_obvody.district_scorecard AS
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov' LIMIT 1
),
latest_verdicts AS (
  SELECT DISTINCT ON (v.district_id, v.condition_code)
    v.id AS verdict_id,
    v.district_id,
    v.condition_code,
    v.value,
    v.confidence,
    v.data_completeness,
    v.methodology_version,
    v.engine_version,
    v.computed_at,
    v.evidence_text,
    v.is_illustrative,
    v.is_proxy,
    v.is_mock,
    (v.provenance->>'source') AS provenance_source_raw,
    (v.provenance->>'fetched_at')::timestamptz AS provenance_fetched_at,
    (v.methodology->>'rule') AS methodology_rule
  FROM skolske_obvody.verdicts v
  JOIN skolske_obvody.districts d ON d.id = v.district_id
  WHERE d.municipality_id = (SELECT id FROM presov)
  ORDER BY v.district_id, v.condition_code, v.computed_at DESC
)
SELECT
  lv.district_id,
  d.name AS district_name,
  d.municipality_id,
  m.name AS municipality_name,
  NULL::uuid AS vzn_id,
  NULL::text AS vzn_ref_url,
  lv.condition_code,
  CASE lv.condition_code
    WHEN 'S1' THEN 'Š1 — Adresy žiakov a obvod'
    WHEN 'S2' THEN 'Š2 — Topologické pokrytie'
    WHEN 'S3' THEN 'Š3 — Kompozícia obvodu'
    WHEN 'Pa' THEN 'P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km'
    WHEN 'Pb' THEN 'P-b — Pešia trasa'
    WHEN 'Pc' THEN 'P-c — MHD dostupnosť'
    WHEN 'Pd' THEN 'P-d — Bariéry (cesty, koľaje)'
    WHEN 'Pe' THEN 'P-e — Sociálny kontext (Atlas MRK)'
    WHEN 'Pf' THEN 'P-f — Demografia detí'
    ELSE lv.condition_code
  END AS condition_label_sk,
  CASE lv.condition_code
    WHEN 'S1' THEN 1 WHEN 'S2' THEN 2 WHEN 'S3' THEN 3
    WHEN 'Pa' THEN 4 WHEN 'Pb' THEN 5 WHEN 'Pc' THEN 6
    WHEN 'Pd' THEN 7 WHEN 'Pe' THEN 8 WHEN 'Pf' THEN 9
    ELSE 99
  END AS condition_order,
  lv.value,
  lv.confidence,
  lv.data_completeness,
  lv.methodology_rule,
  lv.methodology_version,
  CASE WHEN skolske_obvody.host_in_allowlist(lv.provenance_source_raw)
    THEN lv.provenance_source_raw
    ELSE NULL
  END AS provenance_source,
  lv.provenance_fetched_at,
  skolske_obvody.sanitize_evidence(lv.evidence_text, 500) AS evidence_public_text,
  lv.is_illustrative,
  lv.is_proxy,
  lv.is_mock,
  dc.composition_color,
  lv.computed_at
FROM latest_verdicts lv
JOIN skolske_obvody.districts d ON d.id = lv.district_id
JOIN skolske_obvody.municipalities m ON m.id = d.municipality_id
LEFT JOIN skolske_obvody.district_compositions dc ON dc.district_id = lv.district_id;

-- ----- §2.4 municipalities_summary VIEW -----
CREATE OR REPLACE VIEW skolske_obvody.municipalities_summary AS
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov' LIMIT 1
)
SELECT
  m.id AS municipality_id,
  m.name,
  COUNT(DISTINCT d.id) AS districts_count,
  COUNT(DISTINCT d.school_id) AS schools_count,
  COUNT(DISTINCT f.id) FILTER (WHERE f.status = 'open') AS open_findings_count,
  COUNT(DISTINCT dc.district_id) FILTER (WHERE dc.composition_color = 'RED') AS red_districts_count,
  COUNT(DISTINCT dc.district_id) FILTER (WHERE dc.composition_color = 'ORANGE') AS orange_districts_count,
  COUNT(DISTINCT dc.district_id) FILTER (WHERE dc.composition_color = 'GREEN') AS green_districts_count,
  COUNT(DISTINCT dc.district_id) FILTER (WHERE dc.composition_color = 'NONE') AS none_districts_count
FROM skolske_obvody.municipalities m
JOIN skolske_obvody.districts d ON d.municipality_id = m.id
LEFT JOIN skolske_obvody.findings f ON f.district_id = d.id
LEFT JOIN skolske_obvody.district_compositions dc ON dc.district_id = d.id
WHERE m.id = (SELECT id FROM presov)
GROUP BY m.id, m.name;

-- ----- §2.4 findings_public VIEW -----
CREATE OR REPLACE VIEW skolske_obvody.findings_public AS
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov' LIMIT 1
)
SELECT
  f.id AS finding_id,
  f.district_id,
  d.name AS district_name,
  f.municipality_id,
  m.name AS municipality_name,
  f.condition_code,
  CASE f.condition_code
    WHEN 'S1' THEN 'Š1 — Adresy žiakov a obvod'
    WHEN 'S2' THEN 'Š2 — Topologické pokrytie'
    WHEN 'S3' THEN 'Š3 — Kompozícia obvodu'
    WHEN 'Pa' THEN 'P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km'
    WHEN 'Pb' THEN 'P-b — Pešia trasa'
    WHEN 'Pc' THEN 'P-c — MHD dostupnosť'
    WHEN 'Pd' THEN 'P-d — Bariéry (cesty, koľaje)'
    WHEN 'Pe' THEN 'P-e — Sociálny kontext (Atlas MRK)'
    WHEN 'Pf' THEN 'P-f — Demografia detí'
    ELSE f.condition_code
  END AS condition_label_sk,
  f.severity,
  CASE f.severity
    WHEN 'critical' THEN 5
    WHEN 'high' THEN 4
    WHEN 'medium' THEN 3
    WHEN 'low' THEN 2
    ELSE 1
  END AS severity_rank,
  f.status,
  skolske_obvody.sanitize_evidence(f.evidence_text, 200) AS evidence_public_text,
  CASE WHEN skolske_obvody.host_in_allowlist(v.provenance->>'source')
    THEN v.provenance->>'source'
    ELSE NULL
  END AS provenance_source,
  f.created_at
FROM skolske_obvody.findings f
JOIN skolske_obvody.districts d ON d.id = f.district_id
JOIN skolske_obvody.municipalities m ON m.id = f.municipality_id
LEFT JOIN skolske_obvody.verdicts v ON v.id = f.verdict_id
WHERE f.municipality_id = (SELECT id FROM presov);

-- ----- §2.4 engine_metadata VIEW -----
CREATE OR REPLACE VIEW skolske_obvody.engine_metadata AS
WITH presov AS (
  SELECT id FROM skolske_obvody.municipalities WHERE slug = 'presov' LIMIT 1
)
SELECT
  MAX(v.dataset_version) AS dataset_version,
  MAX(v.methodology_version) AS methodology_version,
  MAX(v.engine_version) AS engine_version,
  MAX(v.computed_at) AS last_engine_run_at,
  COUNT(v.id) AS verdicts_count,
  COUNT(DISTINCT d.id) AS districts_count,
  COUNT(DISTINCT d.school_id) AS schools_count,
  COUNT(DISTINCT f.id) FILTER (WHERE f.status = 'open') AS open_findings_count
FROM skolske_obvody.verdicts v
JOIN skolske_obvody.districts d ON d.id = v.district_id
LEFT JOIN skolske_obvody.findings f ON f.district_id = d.id
WHERE d.municipality_id = (SELECT id FROM presov);

-- ----- §2.5 provenance_allowed_hosts VIEW (7th view) -----
CREATE OR REPLACE VIEW skolske_obvody.provenance_allowed_hosts AS
SELECT unnest(ARRAY[
  'slov-lex.sk', 'cvti.sk', 'osm.org', 'openstreetmap.org',
  'geoportal.gov.sk', 'presov.sk', 'gov.sk', 'statistics.sk',
  'atlasromskychkomunit.sk', 'minedu.sk', 'mzv.sk'
]) AS host;

-- ----- §2.5 GRANTs -----
GRANT USAGE ON SCHEMA skolske_obvody TO anon;
GRANT SELECT ON
  skolske_obvody.district_compositions,
  skolske_obvody.district_map_features,
  skolske_obvody.district_scorecard,
  skolske_obvody.municipalities_summary,
  skolske_obvody.findings_public,
  skolske_obvody.engine_metadata,
  skolske_obvody.provenance_allowed_hosts
TO anon;

-- Defensive REVOKE on raw tables (idempotent)
REVOKE ALL ON skolske_obvody.districts FROM anon;
REVOKE ALL ON skolske_obvody.schools FROM anon;
REVOKE ALL ON skolske_obvody.verdicts FROM anon;
REVOKE ALL ON skolske_obvody.findings FROM anon;
REVOKE ALL ON skolske_obvody.municipalities FROM anon;

COMMENT ON SCHEMA skolske_obvody IS 'public read-views only — anon must NOT access raw tables';
