-- 0045_finding_evidence_trail.sql (VLA-15)
-- Evidence trail for street-level verdicts: expose the structured trail the
-- engine writes into verdict.provenance->'evidence_trail' (vzn_citation,
-- register_state, geometry_evidence, conclusion_sk) on findings_public, plus
-- source_public + method_public so every finding shows source + method from
-- the verdict 5-tuple (client feedback 2026-07-06: a verdict without visible
-- reasoning must not be presented as an assertion).
--
-- Rebuilds findings_public (base of 0044 + new columns) and the public
-- wrappers so_findings_public / so_findings_panel. Idempotent.

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
    -- VLA-15: source + method from the verdict 5-tuple, sanitized for public.
    skolske_obvody.sanitize_evidence(v.provenance ->> 'source'::text, 160) AS source_public,
    skolske_obvody.sanitize_evidence(
        COALESCE(v.provenance ->> 'method'::text, v.methodology ->> 'rule'::text),
        240
    ) AS method_public,
    -- VLA-15: structured evidence trail (street-level verdict classes).
    CASE
        WHEN v.provenance ? 'evidence_trail' THEN jsonb_build_object(
            'vzn_citation',
                skolske_obvody.sanitize_evidence(v.provenance -> 'evidence_trail' ->> 'vzn_citation', 500),
            'register_state',
                skolske_obvody.sanitize_evidence(v.provenance -> 'evidence_trail' ->> 'register_state', 500),
            'geometry_evidence',
                skolske_obvody.sanitize_evidence(v.provenance -> 'evidence_trail' ->> 'geometry_evidence', 500),
            'conclusion_sk',
                skolske_obvody.sanitize_evidence(v.provenance -> 'evidence_trail' ->> 'conclusion_sk', 500)
        )
        ELSE NULL::jsonb
    END AS evidence_trail,
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
  fp.source_public,
  fp.method_public,
  fp.evidence_trail,
  fp.created_at,
  fp.is_demo,
  fp.tag,
  public.ST_X(public.ST_Centroid(d.geom)) AS district_geom_centroid_lon,
  public.ST_Y(public.ST_Centroid(d.geom)) AS district_geom_centroid_lat
FROM skolske_obvody.findings_public fp
JOIN skolske_obvody.districts d ON d.id = fp.district_id
WHERE fp.severity IN ('critical', 'high', 'medium');
GRANT SELECT ON public.so_findings_panel TO anon, authenticated, service_role;
