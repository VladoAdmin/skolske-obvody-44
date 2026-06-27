-- 0036_demo_mode_inputs.sql
-- DEMO MODE — per-district complete INPUT layer so EVERY §44 condition produces a
-- decisive, high-confidence verdict for the demo. All values are clearly DEMO
-- (the row itself lives in district_demo_inputs and every verdict it drives is
-- flagged is_mock=TRUE → the UI badges it DEMO). The engine recomputes verdicts
-- from these inputs; no hand-written verdicts, no per-view illustration.
--
-- Real-data honesty preserved: the engine only reads these rows when
-- demo_mode is on AND a row exists for the district. With no demo row the
-- checkers keep their honest INSUFFICIENT_DATA / INCOMPLETE behaviour.
--
-- Idempotent: TRUNCATE + INSERT; safe to re-run.

-- ---------------------------------------------------------------------------
-- Table: one row per district with the demo inputs the checkers read.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skolske_obvody.district_demo_inputs (
    district_id     uuid PRIMARY KEY
                    REFERENCES skolske_obvody.districts(id) ON DELETE CASCADE,
    -- S1: address coverage demo (uncovered / multi-assigned counts).
    s1_total_addresses   integer,
    s1_uncovered         integer,
    s1_wrong_district    integer,   -- address-in-wrong-district (S1 violation type)
    -- S2: whether this district is a demo overlap partner (FALSE = clean topology).
    s2_overlap           boolean,
    -- S3: number of public schools the demo places inside this district (1 = ok).
    s3_school_count      integer,
    -- Pa: farthest demo address distance (m). > 2000 = FAIL.
    pa_max_distance_m    numeric,
    -- Pc: number of transfers on the modelled MHD route. >= 2 = poor (FAIL).
    pc_transfers         integer,
    pc_total_minutes     integer,
    -- Pd: barrier on the home->school route (busy road / rail without crossing).
    pd_barrier           boolean,
    pd_barrier_kind      text,      -- 'cesta I. triedy' | 'železnica' | NULL
    -- Pe: marginalized-community locality signal seeded for this district.
    pe_mrk_signal        boolean,
    -- Pf: school capacity vs enrolment demo.
    pf_capacity          integer,
    pf_enrolment         integer,
    -- JAZYK: minority teaching language podnet (outside §44).
    jazyk_language       text,      -- e.g. 'HU' | NULL
    note                 text,
    created_at           timestamptz NOT NULL DEFAULT now()
);

-- A municipality-level switch so the engine knows demo mode is active.
-- engine_metadata is a view in some envs; use a dedicated tiny table instead.
CREATE TABLE IF NOT EXISTS skolske_obvody.demo_mode_flag (
    municipality_id uuid PRIMARY KEY,
    enabled         boolean NOT NULL DEFAULT true,
    updated_at      timestamptz NOT NULL DEFAULT now()
);

INSERT INTO skolske_obvody.demo_mode_flag (municipality_id, enabled)
SELECT id, true FROM skolske_obvody.municipalities WHERE slug = 'presov'
ON CONFLICT (municipality_id) DO UPDATE SET enabled = TRUE, updated_at = now();

-- ---------------------------------------------------------------------------
-- Seed every Prešov district. Distribution (criterion 3): 4 RED, 2 ORANGE, 6 GREEN.
--   RED:    Bajkalská (S1+Pa), Kúpeľná (S2), Sibírska (S2+Pf), Šmeralova (S3)
--   ORANGE: Lesnícka (Pc), Československej (Pd)
--   GREEN:  Námestie, Májové, Prostějovská, Mirka Nešpora (all PASS),
--           Šrobárova (Pe SIGNAL — signal panel, stays GREEN legally),
--           Važecká (JAZYK podnet — outside §44, stays GREEN)
-- ---------------------------------------------------------------------------
TRUNCATE skolske_obvody.district_demo_inputs;

INSERT INTO skolske_obvody.district_demo_inputs (
    district_id, s1_total_addresses, s1_uncovered, s1_wrong_district,
    s2_overlap, s3_school_count, pa_max_distance_m,
    pc_transfers, pc_total_minutes, pd_barrier, pd_barrier_kind,
    pe_mrk_signal, pf_capacity, pf_enrolment, jazyk_language, note
)
SELECT d.id,
    v.s1_total_addresses, v.s1_uncovered, v.s1_wrong_district,
    v.s2_overlap, v.s3_school_count, v.pa_max_distance_m,
    v.pc_transfers, v.pc_total_minutes, v.pd_barrier, v.pd_barrier_kind,
    v.pe_mrk_signal, v.pf_capacity, v.pf_enrolment, v.jazyk_language, v.note
FROM (VALUES
    -- name, s1_total, s1_uncov, s1_wrong, s2_ovl, s3_cnt, pa_max, pc_tr, pc_min, pd_barr, pd_kind, pe, pf_cap, pf_enr, jazyk, note
    ('Základná škola, Bajkalská č. 29',
        820, 0, 14, false, 1, 2480::numeric, 1, 18, false, NULL, false, 640, 590, NULL,
        'DEMO RED: 14 adries priradených do nesprávneho obvodu (S1 FAIL) + najvzdialenejšia adresa 2480 m > 2 km (Pa FAIL).'),
    ('Základná škola, Kúpeľná č. 2',
        540, 0, 0, true, 1, 1450::numeric, 1, 16, false, NULL, false, 480, 430, NULL,
        'DEMO RED: prekryv obvodu so Sibírskou (S2 FAIL — dvojité pokrytie ulíc).'),
    ('Základná škola, Sibírska č. 42',
        610, 0, 0, true, 1, 1620::numeric, 1, 20, false, NULL, false, 560, 712, NULL,
        'DEMO RED: prekryv s Kúpeľnou (S2 FAIL) + preťaženie 712/560 (Pf SIGNAL).'),
    ('Základná škola, Šmeralova č. 25',
        700, 0, 0, false, 2, 1780::numeric, 1, 22, false, NULL, false, 620, 540, NULL,
        'DEMO RED: dve verejné školy v jednom obvode (S3 FAIL).'),
    ('Základná škola, Lesnícka č. 1',
        430, 0, 0, false, 1, 1390::numeric, 2, 41, false, NULL, false, 500, 460, NULL,
        'DEMO ORANGE: MHD trasa s 2 prestupmi a 41 min (Pc FAIL — indikátor).'),
    ('Základná škola, Československej armády č. 22',
        560, 0, 0, false, 1, 1510::numeric, 1, 19, true, 'železnica bez podchodu', false, 520, 470, NULL,
        'DEMO ORANGE: trasa kríži železnicu bez podchodu (Pd FAIL — indikátor).'),
    ('Základná škola, Šrobárova č. 20',
        480, 0, 0, false, 1, 1280::numeric, 1, 15, false, NULL, true, 510, 440, NULL,
        'DEMO GREEN (so signálom): lokalita MRK v obvode (Pe SIGNAL — analytický panel, nezhorší semafor).'),
    ('Základná škola, Važecká č. 11',
        390, 0, 0, false, 1, 1190::numeric, 1, 14, false, NULL, false, 470, 410, 'HU',
        'DEMO GREEN: pridelená škola vyučuje v HU (JAZYK podnet — mimo §44, nie v semafore).'),
    ('Základná škola s materskou školou, Námestie Kráľovnej pokoja 4',
        510, 0, 0, false, 1, 980::numeric, 1, 13, false, NULL, false, 500, 420, NULL,
        'DEMO GREEN: všetky §44 podmienky PASS.'),
    ('Základná škola, Májové námestie č. 1',
        450, 0, 0, false, 1, 760::numeric, 0, 11, false, NULL, false, 480, 390, NULL,
        'DEMO GREEN: všetky §44 podmienky PASS.'),
    ('Základná škola, Prostějovská č. 38',
        470, 0, 0, false, 1, 1620::numeric, 1, 17, false, NULL, false, 520, 450, NULL,
        'DEMO GREEN: všetky §44 podmienky PASS.'),
    ('Základná škola, Mirka Nešpora č. 2',
        500, 0, 0, false, 1, 1340::numeric, 1, 16, false, NULL, false, 510, 430, NULL,
        'DEMO GREEN: všetky §44 podmienky PASS.')
) AS v(name, s1_total_addresses, s1_uncovered, s1_wrong_district,
       s2_overlap, s3_school_count, pa_max_distance_m,
       pc_transfers, pc_total_minutes, pd_barrier, pd_barrier_kind,
       pe_mrk_signal, pf_capacity, pf_enrolment, jazyk_language, note)
JOIN skolske_obvody.districts d ON d.name = v.name;
