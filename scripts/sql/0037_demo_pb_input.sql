-- 0037_demo_pb_input.sql
-- Add a demo P-b (walking time/distance) input so P-b is also decisive and
-- high-confidence in demo mode instead of relying on live OSRM (which yields
-- low-confidence RISK results uncurated for the demo). Idempotent.

ALTER TABLE skolske_obvody.district_demo_inputs
    ADD COLUMN IF NOT EXISTS pb_minutes        integer,
    ADD COLUMN IF NOT EXISTS pb_distance_m     numeric;

-- Curated P-b values. Thresholds (constants.py): PASS <= 2000 m AND <= 1800 s;
-- RISK <= 4000 m; FAIL > 4000 m. ">30 min" walking is the P-b violation type
-- (Lesnícka, demonstrating §44 ods. 8 písm. b). Everyone else PASS.
UPDATE skolske_obvody.district_demo_inputs di
SET pb_minutes = v.mins, pb_distance_m = v.dist
FROM (VALUES
    ('Základná škola, Lesnícka č. 1',                                   38, 2900::numeric),  -- RISK: >30 min (Pb violation type)
    ('Základná škola, Bajkalská č. 29',                                 24, 1850::numeric),
    ('Základná škola, Kúpeľná č. 2',                                    16, 1200::numeric),
    ('Základná škola, Sibírska č. 42',                                  20, 1500::numeric),
    ('Základná škola, Šmeralova č. 25',                                 22, 1650::numeric),
    ('Základná škola, Československej armády č. 22',                     19, 1450::numeric),
    ('Základná škola, Šrobárova č. 20',                                 15, 1100::numeric),
    ('Základná škola, Važecká č. 11',                                   14, 1050::numeric),
    ('Základná škola s materskou školou, Námestie Kráľovnej pokoja 4',  13, 980::numeric),
    ('Základná škola, Májové námestie č. 1',                            11, 760::numeric),
    ('Základná škola, Prostějovská č. 38',                              17, 1300::numeric),
    ('Základná škola, Mirka Nešpora č. 2',                              16, 1250::numeric)
) AS v(name, mins, dist)
JOIN skolske_obvody.districts d ON d.name = v.name
WHERE di.district_id = d.id;
