-- 0044_legal_audit_labels.sql
-- VLA-19 legal audit § 44: view label CASEs must mirror lib/compliance/labels.ts.
-- Three labels corrected (see docs/legal-audit-44.md):
--   Pa    'P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km' -> 'P-a — Vzdialenosť (vzdušná čiara)'
--         (2 km is a demo methodological parameter, not a legal limit — § 44
--          ods. 8 písm. b) sets no number; old label read as a legal norm)
--   S2    'Š2 — Topologické pokrytie' -> 'Š2 — Neprekrývanie obvodov'
--         (engine tests address-level overlap per § 44 ods. 1 a 7, not polygon topology)
--   JAZYK 'Podnet nad rámec § 44 (jazyk)' -> 'Jazykový podnet (mimo semaforu)'
--         (language IS a § 44 ods. 8 písm. d) factor; it stays outside the semafor)
-- View bodies otherwise identical to 0033. Idempotent.

CREATE OR REPLACE VIEW skolske_obvody.district_scorecard AS
 WITH presov AS (
         SELECT municipalities.id
           FROM skolske_obvody.municipalities
          WHERE municipalities.slug = 'presov'::text
         LIMIT 1
        ), latest_verdicts AS (
         SELECT DISTINCT ON (v.district_id, v.condition_code) v.id AS verdict_id,
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
            v.provenance ->> 'source'::text AS provenance_source_raw,
            (v.provenance ->> 'fetched_at'::text)::timestamp with time zone AS provenance_fetched_at,
            v.methodology ->> 'rule'::text AS methodology_rule
           FROM skolske_obvody.verdicts v
             JOIN skolske_obvody.districts d_1 ON d_1.id = v.district_id
          WHERE d_1.municipality_id = (( SELECT presov.id FROM presov))
          ORDER BY v.district_id, v.condition_code, v.computed_at DESC
        )
 SELECT lv.district_id,
    d.name AS district_name,
    d.municipality_id,
    m.name AS municipality_name,
    NULL::uuid AS vzn_id,
    NULL::text AS vzn_ref_url,
    lv.condition_code,
        CASE lv.condition_code
            WHEN 'S1'::text THEN 'Š1 — Adresy žiakov a obvod'::text
            WHEN 'S2'::text THEN 'Š2 — Neprekrývanie obvodov'::text
            WHEN 'S3'::text THEN 'Š3 — Kompozícia obvodu'::text
            WHEN 'Pa'::text THEN 'P-a — Vzdialenosť (vzdušná čiara)'::text
            WHEN 'Pb'::text THEN 'P-b — Pešia trasa'::text
            WHEN 'Pc'::text THEN 'P-c — MHD dostupnosť'::text
            WHEN 'Pd'::text THEN 'P-d — Bariéry (cesty, koľaje)'::text
            WHEN 'Pe'::text THEN 'P-e — Sociálny kontext (Atlas MRK)'::text
            WHEN 'Pf'::text THEN 'P-f — Demografia detí'::text
            WHEN 'JAZYK'::text THEN 'Jazykový podnet (mimo semaforu)'::text
            ELSE lv.condition_code
        END AS condition_label_sk,
        CASE lv.condition_code
            WHEN 'S1'::text THEN 1
            WHEN 'S2'::text THEN 2
            WHEN 'S3'::text THEN 3
            WHEN 'Pa'::text THEN 4
            WHEN 'Pb'::text THEN 5
            WHEN 'Pc'::text THEN 6
            WHEN 'Pd'::text THEN 7
            WHEN 'Pe'::text THEN 8
            WHEN 'Pf'::text THEN 9
            WHEN 'JAZYK'::text THEN 10
            ELSE 99
        END AS condition_order,
    lv.value,
    lv.confidence,
    lv.data_completeness,
    lv.methodology_rule,
    lv.methodology_version,
        CASE
            WHEN skolske_obvody.host_in_allowlist(lv.provenance_source_raw) THEN lv.provenance_source_raw
            ELSE NULL::text
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

GRANT SELECT ON skolske_obvody.district_scorecard TO anon, authenticated, service_role;

-- public wrapper
DROP VIEW IF EXISTS public.so_district_scorecard CASCADE;
CREATE VIEW public.so_district_scorecard AS SELECT * FROM skolske_obvody.district_scorecard;
GRANT SELECT ON public.so_district_scorecard TO anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- findings_public — add JAZYK label + recreate panel wrapper
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS skolske_obvody.findings_public CASCADE;

CREATE VIEW skolske_obvody.findings_public AS
WITH presov AS (
    SELECT municipalities.id
    FROM skolske_obvody.municipalities
    WHERE municipalities.slug = 'presov'::text
    LIMIT 1
),
current_run AS (
    SELECT engine_version
    FROM skolske_obvody.findings
    WHERE engine_version IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 1
)
SELECT f.id AS finding_id,
    f.district_id,
    d.name AS district_name,
    f.municipality_id,
    m.name AS municipality_name,
    f.condition_code,
    CASE f.condition_code
        WHEN 'S1'::text THEN 'Š1 — Adresy žiakov a obvod'::text
        WHEN 'S2'::text THEN 'Š2 — Neprekrývanie obvodov'::text
        WHEN 'S3'::text THEN 'Š3 — Kompozícia obvodu'::text
        WHEN 'Pa'::text THEN 'P-a — Vzdialenosť (vzdušná čiara)'::text
        WHEN 'Pb'::text THEN 'P-b — Pešia trasa'::text
        WHEN 'Pc'::text THEN 'P-c — MHD dostupnosť'::text
        WHEN 'Pd'::text THEN 'P-d — Bariéry (cesty, koľaje)'::text
        WHEN 'Pe'::text THEN 'P-e — Sociálny kontext (Atlas MRK)'::text
        WHEN 'Pf'::text THEN 'P-f — Demografia detí'::text
        WHEN 'JAZYK'::text THEN 'Jazykový podnet (mimo semaforu)'::text
        ELSE f.condition_code
    END AS condition_label_sk,
    f.severity,
    CASE f.severity
        WHEN 'critical'::text THEN 5
        WHEN 'high'::text THEN 4
        WHEN 'medium'::text THEN 3
        WHEN 'low'::text THEN 2
        ELSE 1
    END AS severity_rank,
    f.status,
    skolske_obvody.sanitize_evidence(f.evidence_text, 200) AS evidence_public_text,
    CASE
        WHEN skolske_obvody.host_in_allowlist(v.provenance ->> 'source'::text)
            THEN v.provenance ->> 'source'::text
        ELSE NULL::text
    END AS provenance_source,
    f.created_at,
    f.is_demo,
    f.tag
FROM skolske_obvody.findings f
    JOIN skolske_obvody.districts d ON d.id = f.district_id
    JOIN skolske_obvody.municipalities m ON m.id = f.municipality_id
    LEFT JOIN skolske_obvody.verdicts v ON v.id = f.verdict_id
WHERE f.municipality_id = ((SELECT presov.id FROM presov))
  AND f.engine_version = (SELECT engine_version FROM current_run);

GRANT SELECT ON skolske_obvody.findings_public TO anon, authenticated, service_role;

DROP VIEW IF EXISTS public.so_findings_public CASCADE;
CREATE VIEW public.so_findings_public AS SELECT * FROM skolske_obvody.findings_public;
GRANT SELECT ON public.so_findings_public TO anon, authenticated, service_role;

DROP VIEW IF EXISTS public.so_findings_panel CASCADE;
CREATE VIEW public.so_findings_panel AS
SELECT
  fp.finding_id,
  fp.district_id,
  fp.district_name,
  fp.municipality_id,
  fp.municipality_name,
  fp.condition_code,
  fp.condition_label_sk,
  fp.severity,
  fp.severity_rank,
  fp.status,
  fp.evidence_public_text,
  fp.provenance_source,
  fp.created_at,
  fp.is_demo,
  fp.tag,
  public.ST_X(public.ST_Centroid(d.geom)) AS district_geom_centroid_lon,
  public.ST_Y(public.ST_Centroid(d.geom)) AS district_geom_centroid_lat
FROM skolske_obvody.findings_public fp
JOIN skolske_obvody.districts d ON d.id = fp.district_id
WHERE fp.severity IN ('critical', 'high', 'medium');
GRANT SELECT ON public.so_findings_panel TO anon, authenticated, service_role;
