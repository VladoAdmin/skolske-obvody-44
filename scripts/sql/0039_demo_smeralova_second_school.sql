-- 0039_demo_smeralova_second_school.sql
-- Item 18 — the Šmeralova finding asserts the obvod contains MORE THAN ONE
-- school (S3 structural FAIL, driven by demo input s3_school_count=2 in
-- 0036_demo_mode_inputs.sql), but the map showed only one school → finding and
-- map disagreed.
--
-- Fix: seed a SECOND public-school marker INSIDE the Šmeralova obvod, clearly
-- DEMO-flagged, so the map actually renders two public schools matching the S3
-- FAIL. The school is added through the proper data path (skolske_obvody.schools
-- + the so_school_markers view that the map reads), NOT injected into the
-- display layer. The S3 FAIL itself comes from a legal structural condition, so
-- this is allowed under the invariants (mock seeds a demonstrable structural
-- FAIL, it does not fabricate a RED verdict in the display layer).
--
-- The interior coordinate (21.2537726, 49.0254904) is ST_PointOnSurface of the
-- Šmeralova polygon, so the second school is guaranteed to sit inside the obvod.
--
-- Idempotent: adds is_demo column if missing, then UPSERTs the demo school by a
-- stable eduid.

ALTER TABLE skolske_obvody.schools
    ADD COLUMN IF NOT EXISTS is_demo boolean NOT NULL DEFAULT false;

-- Remove any prior demo school for this obvod (keep re-runs clean).
DELETE FROM skolske_obvody.schools
 WHERE is_demo = true AND eduid = 'DEMO-SMERALOVA-2';

INSERT INTO skolske_obvody.schools
    (id, founder_id, municipality_id, eduid, name, type, is_public,
     teaching_language, capacity, student_count, geom, source_name, is_demo, metadata)
VALUES (
    gen_random_uuid(),
    '835c40b4-974c-4ec7-896b-dcb13b0f9065'::uuid,  -- same founder as ZŠ Šmeralova
    'e74cc008-e6e3-4b4d-abae-0c62d240ba01'::uuid,  -- Prešov
    'DEMO-SMERALOVA-2',
    'Základná škola, Tehelná č. 3 (DEMO)',
    'ZS',
    true,                                          -- PUBLIC → counts toward S3
    'SK',
    520,
    480,
    public.ST_SetSRID(public.ST_MakePoint(21.2537726132556, 49.0254903941845), 4326),
    'DEMO seed (item 18) — second public school for Šmeralova S3 FAIL',
    true,
    jsonb_build_object('demo', true, 'reason', 'S3 FAIL — two public schools in one obvod')
);
