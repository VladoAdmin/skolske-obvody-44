-- 0045_demo_barriers.sql
-- VLA-20 (client defect 2) — barrier INPUT table + fictional demo railway.
--
-- WHY
--   The client removed the "nedostatočné dáta" state entirely: the engine must
--   ALWAYS have an input for the P-d barrier condition. Real railway/crossing
--   data is not available, so we seed a FICTIONAL railway line (is_demo=TRUE)
--   as explicit input data. The engine evaluates P-d against this table when a
--   district has no district_demo_inputs row; the GUI renders the line with a
--   DEMO badge (fabricated data always carries is_demo → DEMO badge invariant).
--
--   The fictional line is placed so it crosses ONLY the district of
--   ZŠ Československej armády č. 22 — consistent with the existing demo
--   scenario (district_demo_inputs.pd_barrier=TRUE only there, "železnica bez
--   podchodu"); all other districts stay PASS.
--
-- WHAT
--   * skolske_obvody.barriers — INPUT table (engine reads, GUI reads via view)
--   * public.so_barriers      — PostgREST read view (GeoJSON)
--   * seed: 1 fictional railway LineString, is_demo=TRUE
--
-- Apply:  python3 scripts/apply_sql.py scripts/sql/0045_demo_barriers.sql
-- Then:   SO_EMIT_FINDINGS=1 python3 -m engine.runner

CREATE TABLE IF NOT EXISTS skolske_obvody.barriers (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  municipality_id UUID NOT NULL,
  kind            TEXT NOT NULL CHECK (kind IN ('railway', 'road')),
  name            TEXT NOT NULL,
  geom            public.geometry(LineString, 4326) NOT NULL,
  is_demo         BOOLEAN NOT NULL DEFAULT FALSE,
  reason_sk       TEXT,             -- popup text (Slovak)
  provenance      JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS barriers_mun_idx
  ON skolske_obvody.barriers (municipality_id);

-- Public read view (PostgREST does not expose the skolske_obvody schema).
DROP VIEW IF EXISTS public.so_barriers;
CREATE VIEW public.so_barriers AS
SELECT
  b.kind,
  b.name,
  b.is_demo,
  b.reason_sk,
  public.ST_AsGeoJSON(b.geom)::jsonb AS geom_geojson
FROM skolske_obvody.barriers b;

GRANT SELECT ON public.so_barriers TO anon, authenticated, service_role;

-- Seed: fictional railway through the ZŠ Československej armády district
-- (western Prešov). Idempotent: demo rows are replaced wholesale.
DELETE FROM skolske_obvody.barriers WHERE is_demo = TRUE;

INSERT INTO skolske_obvody.barriers
  (municipality_id, kind, name, geom, is_demo, reason_sk, provenance)
VALUES (
  'e74cc008-e6e3-4b4d-abae-0c62d240ba01',
  'railway',
  'Železničná trať bez podchodu (DEMO — fiktívna bariéra)',
  public.ST_GeomFromText(
    'LINESTRING(21.163 48.952, 21.172 48.965, 21.181 48.980, 21.193 48.998)',
    4326
  ),
  TRUE,
  'Ukážková (DEMO) bariéra: fiktívna železničná trať bez podchodu. '
  || 'Slúži ako vstup pre indikátor P-d (bariéry na trase domov→škola). '
  || 'Nejde o reálnu infraštruktúru ani o porušenie § 44.',
  jsonb_build_object(
    'source', 'DEMO — fiktívna bariéra (VLA-20, klient 2026-07-06)',
    'demo', true,
    'note', 'invented input so the P-d barrier condition is always evaluable'
  )
);
