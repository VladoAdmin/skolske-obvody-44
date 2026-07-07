-- 0032_demo_inputs_seed.sql
-- Part B — DEMO INPUT layer. Fabricated content enters ONLY through these real
-- input columns (all flagged is_demo / metadata.*_is_demo). The engine recomputes
-- verdicts from them; views render the engine output. No hand-written verdicts.
--
-- Distribution (clear spread; real findings kept, demos clearly badged):
--   S3  Kompozícia    : REAL FAIL — Mirka Nešpora + Prostějovská share one school. (no seed)
--   Pa  ≤2km          : REAL FAIL — Bajkalská 2155 m, Šmeralova 2060 m (real geocodes).
--   Pf  Demografia    : DEMO — ZŠ Sibírska capacity 560 vs enrolment 712 → SIGNAL.
--   Pe  Soc. kontext  : DEMO — ZŠ Šrobárova obvod seeded with MRK locality buildings.
--   Jazyk (mimo §44)  : DEMO — ZŠ Važecká teaching_language='HU' → podnet nad rámec §44.
--   S2  Topológia     : handled by 0033 (engine-read demo overlap layer).
--
-- Idempotent: each block clears its own demo rows / resets its own flag first.

-- ---------------------------------------------------------------------------
-- Pf — overcrowding DEMO on ZŠ Sibírska (matched by district name).
-- ---------------------------------------------------------------------------
UPDATE skolske_obvody.schools s
SET capacity = 560,
    student_count = 712,
    metadata = COALESCE(s.metadata, '{}'::jsonb)
               || jsonb_build_object(
                    'pf_capacity_is_demo', true,
                    'pf_demo_note', 'DEMO: fabricated capacity/enrolment to demonstrate § 44 ods. 8 písm. a) capacity overload'
                  )
WHERE s.id = (
    SELECT d.school_id FROM skolske_obvody.districts d
    WHERE d.name = 'Základná škola, Sibírska č. 42'
    LIMIT 1
);

-- ---------------------------------------------------------------------------
-- Jazyk (podnet nad rámec § 44) — DEMO minority teaching language on ZŠ Važecká.
-- A real geometric statement becomes possible: minority pupils' nearest school
-- teaches only in SK, so an HU-teaching school is a separate non-§44 podnet.
-- Stored on the school + a demo flag in metadata; the engine emits a non-§44
-- "jazyk" finding (NOT under Pd).
-- ---------------------------------------------------------------------------
UPDATE skolske_obvody.schools s
SET teaching_language = 'HU',
    metadata = COALESCE(s.metadata, '{}'::jsonb)
               || jsonb_build_object(
                    'lang_is_demo', true,
                    'lang_demo_note', 'DEMO: minority teaching language to demonstrate a non-§44 jazyk podnet'
                  )
WHERE s.id = (
    SELECT d.school_id FROM skolske_obvody.districts d
    WHERE d.name = 'Základná škola, Važecká č. 11'
    LIMIT 1
);

-- ---------------------------------------------------------------------------
-- Pe — DEMO MRK locality buildings inside ZŠ Šrobárova obvod (explicit inclusion
-- case). We place MRK_BUILDING_SIGNAL_MIN+ demo building points inside the
-- district polygon so the engine raises a real per-district Pe SIGNAL, flagged
-- is_demo. Points are jittered around the district centroid (guaranteed inside).
-- ---------------------------------------------------------------------------
DELETE FROM skolske_obvody.mrk_buildings WHERE is_demo = true;

INSERT INTO skolske_obvody.mrk_buildings (id, obec, geom, is_demo, provenance)
SELECT
    gen_random_uuid(),
    'Prešov',
    public.ST_SetSRID((public.ST_Dump(public.ST_GeneratePoints(d.geom, 10))).geom, 4326),
    true,
    jsonb_build_object(
        'layer', 'DEMO inklúzia',
        'note', 'DEMO: fabricated MRK locality to demonstrate § 44 ods. 8 písm. e) segregation-ban case'
    )
FROM skolske_obvody.districts d
WHERE d.name = 'Základná škola, Šrobárova č. 20';
