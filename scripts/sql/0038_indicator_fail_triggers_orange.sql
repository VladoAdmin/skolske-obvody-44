-- 0038_indicator_fail_triggers_orange.sql
-- Mirror engine/compose.py: an INDICATOR (Pa/Pb/Pc/Pd) that FAILs is a real §44
-- risk and must push the semafor to ORANGE (never RED — legal status stays Š1–Š3).
-- Previously the district_compositions view only treated RISK/INSUFFICIENT_DATA as
-- ORANGE triggers, so an indicator FAIL (e.g. Pd barrier, Pc >=2 transfers) was
-- silently GREEN. This adds 'FAIL' to the indicator trigger set.
--
-- Idempotent (CREATE OR REPLACE VIEW). Only the indicators CTE changes.

CREATE OR REPLACE VIEW skolske_obvody.district_compositions AS
 WITH presov AS (
         SELECT municipalities.id
           FROM skolske_obvody.municipalities
          WHERE municipalities.slug = 'presov'::text
         LIMIT 1
        ), latest AS (
         SELECT DISTINCT ON (v.district_id, v.condition_code) v.district_id,
            v.condition_code,
            v.value,
            v.is_illustrative,
            v.engine_version,
            v.methodology_version,
            v.computed_at
           FROM skolske_obvody.verdicts v
             JOIN skolske_obvody.districts d_1 ON d_1.id = v.district_id
          WHERE d_1.municipality_id = (( SELECT presov.id FROM presov))
          ORDER BY v.district_id, v.condition_code, v.computed_at DESC
        ), legal AS (
         SELECT latest.district_id,
            bool_or(latest.value = 'FAIL'::text) AS any_fail,
            bool_or(latest.value = 'INCOMPLETE'::text) AS any_incomplete
           FROM latest
          WHERE latest.condition_code = ANY (ARRAY['S1'::text, 'S2'::text, 'S3'::text])
          GROUP BY latest.district_id
        ), indicators AS (
         SELECT latest.district_id,
            bool_or(latest.value = ANY (ARRAY['RISK'::text, 'INSUFFICIENT_DATA'::text, 'FAIL'::text])) AS any_indicator_risk
           FROM latest
          WHERE (latest.condition_code = ANY (ARRAY['Pa'::text, 'Pb'::text, 'Pc'::text, 'Pd'::text])) AND NOT latest.is_illustrative
          GROUP BY latest.district_id
        ), meta AS (
         SELECT latest.district_id,
            max(latest.engine_version) AS engine_version,
            max(latest.methodology_version) AS methodology_version,
            max(latest.computed_at) AS computed_at
           FROM latest
          GROUP BY latest.district_id
        )
 SELECT d.id AS district_id,
        CASE
            WHEN l.district_id IS NULL THEN 'NONE'::text
            WHEN l.any_fail THEN 'RED'::text
            WHEN l.any_incomplete OR COALESCE(i.any_indicator_risk, false) THEN 'ORANGE'::text
            ELSE 'GREEN'::text
        END AS composition_color,
        CASE
            WHEN l.district_id IS NULL THEN 'Bez verdiktov'::text
            WHEN l.any_fail THEN 'FAIL v zákonných podmienkach'::text
            WHEN l.any_incomplete AND COALESCE(i.any_indicator_risk, false) THEN 'NEÚPLNÉ zákonné podmienky; Rizikové indikátory'::text
            WHEN l.any_incomplete THEN 'NEÚPLNÉ zákonné podmienky'::text
            WHEN COALESCE(i.any_indicator_risk, false) THEN 'Rizikové indikátory'::text
            ELSE 'Š1–Š3 PASS, žiadne rizikové indikátory'::text
        END AS composition_reason,
    jsonb_build_object('legal_fail', COALESCE(l.any_fail, false), 'legal_incomplete', COALESCE(l.any_incomplete, false), 'indicator_risk', COALESCE(i.any_indicator_risk, false)) AS composition_details,
    m.engine_version,
    m.methodology_version,
    m.computed_at
   FROM skolske_obvody.districts d
     LEFT JOIN legal l ON l.district_id = d.id
     LEFT JOIN indicators i ON i.district_id = d.id
     LEFT JOIN meta m ON m.district_id = d.id
  WHERE d.municipality_id = (( SELECT presov.id FROM presov));
