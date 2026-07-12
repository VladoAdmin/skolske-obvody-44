-- 0052_atlas_roma_share.sql
-- VLA-33 — real Atlas rómskych komunít data (ÚSVRK), obec-level Roma
-- population share for Okres Prešov. NEW, SEPARATE, REAL data layer — do
-- NOT confuse with so_mrk_localities (0038/0047), which stays a DEMO/mock
-- street/building-level layer scoped to Prešov city (is_demo=true).
--
-- SOURCE
--   Atlas rómskych komunít 2019 (Úrad splnomocnenca vlády SR pre rómske
--   komunity) — the latest published edition; SMARK 2025 (the planned
--   successor) has not published a results database as of this migration,
--   only questionnaires + a municipality list (verified live 2026-07-12).
--   Public XLSX: https://www.romovia.vlada.gov.sk/site/assets/files/1111/ark2019_c_verejna.xlsx
--   Methodology: https://www.romovia.vlada.gov.sk/site/assets/files/1111/manual_k_verejnej_databaze_atlasu_romskych_komunit_2019_final.docx
--   Downloaded: 2026-07-12. Full provenance + methodology notes in
--   docs/data-sources/atlas-romskych-komunit.md.
--
--   Sheet "obce" (825 municipalities nationwide), column F "Podiel rómskych
--   obyvateľov (intervaly)" — the manual defines this as "Approximately what
--   % of the municipality's population is Roma", published only as 10-point
--   bands (1%-10%, 11%-20%, ... 91%-100%), never an exact %. This migration
--   ingests all 32 Okres Prešov municipalities present in the Atlas (every
--   row the Atlas itself lists for this okres) — not just the ones above
--   any threshold — so the threshold can move without re-ingesting data.
--   roma_share_band_low is the parsed lower bound of that band (e.g.
--   '31%-40%' -> 31); comparing ">" a threshold on this bound is
--   conservative — a municipality only counts as "> X%" once even its
--   band's lower bound clears X.
--
-- CONFIG (AC: threshold must be configurable, not hardcoded in a component)
--   skolske_obvody.atlas_roma_share_config is a singleton row read by the
--   view below; so_atlas_roma_municipalities already applies the filter,
--   and re-exposes the live threshold value per row so the UI never
--   hardcodes "20%" either.
--
-- SCHOOL-DISTRICT LINK
--   This app's skolske_obvody.districts rows are exclusively the 12 Prešov
--   city školské obvody (every districts.municipality_id is Prešov's own
--   id — verified live) plus, per VZN, a fixed set of neighbouring
--   municipalities pooled into one of those districts' catchments
--   (so_shared_municipality_areas, 0050/0051). A village is therefore
--   "assigned to a školský obvod" in this dataset ONLY if it appears in
--   that shared-catchment view — there is no general obec->school-district
--   registry for the rest of Okres Prešov here. assigned_district_id/name
--   is NULL, not fabricated, for the (majority of) highlighted
--   municipalities with no VZN-shared assignment in this app; the UI must
--   show that honestly (same no-fabrication precedent as 0051).
--
-- Idempotent: CREATE TABLE IF NOT EXISTS; TRUNCATE + re-INSERT the ingested
-- rows (safe re-run — content is fully derived from the external file, not
-- user-edited); config row inserted ON CONFLICT DO NOTHING so a live-tuned
-- threshold survives a re-run of this migration.
--
-- Apply: python3 scripts/apply_sql.py scripts/sql/0052_atlas_roma_share.sql

CREATE TABLE IF NOT EXISTS skolske_obvody.atlas_roma_share (
    municipality_id      uuid PRIMARY KEY REFERENCES skolske_obvody.municipalities(id),
    obec_name            text NOT NULL,
    obec_kod             integer NOT NULL,
    okres                text NOT NULL,
    kraj                 text NOT NULL,
    population           integer,
    roma_share_band      text NOT NULL,     -- e.g. '31%-40%', verbatim from the Atlas
    roma_share_band_low  smallint NOT NULL, -- parsed lower bound, e.g. 31
    atlas_year           smallint NOT NULL DEFAULT 2019,
    source_name          text NOT NULL DEFAULT 'Atlas rómskych komunít 2019 (ÚSVRK)',
    source_url           text NOT NULL DEFAULT 'https://www.romovia.vlada.gov.sk/site/assets/files/1111/ark2019_c_verejna.xlsx',
    downloaded_at         date NOT NULL DEFAULT '2026-07-12',
    created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS skolske_obvody.atlas_roma_share_config (
    id                       smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    highlight_threshold_pct  numeric NOT NULL DEFAULT 20,
    updated_at               timestamptz NOT NULL DEFAULT now()
);

INSERT INTO skolske_obvody.atlas_roma_share_config (id, highlight_threshold_pct)
VALUES (1, 20)
ON CONFLICT (id) DO NOTHING;

TRUNCATE skolske_obvody.atlas_roma_share;

INSERT INTO skolske_obvody.atlas_roma_share (
    municipality_id, obec_name, obec_kod, okres, kraj, population,
    roma_share_band, roma_share_band_low
)
SELECT m.id, v.obec_name, v.obec_kod, 'Prešov', 'Prešovský', v.population,
       v.roma_share_band, v.roma_share_band_low
FROM (VALUES
    ('Abranovce', 524158, 694, '31%-40%', 31),
    ('Bzenov', 524263, 735, '11%-20%', 11),
    ('Chmeľov', 524506, 1048, '21%-30%', 21),
    ('Chminianske Jakubovany', 524531, 2631, '81%-90%', 81),
    ('Chmiňany', 524549, 988, '61%-70%', 61),
    ('Drienov', 524352, 2215, '11%-20%', 11),
    ('Drienovská Nová Ves', 524361, 796, '11%-20%', 11),
    ('Fričovce', 524409, 1148, '11%-20%', 11),
    ('Hermanovce', 524468, 1685, '31%-40%', 31),
    ('Kapušany', 524620, 2152, '1%-10%', 1),
    ('Kendice', 524638, 1989, '21%-30%', 21),
    ('Kojatice', 524654, 1143, '11%-20%', 11),
    ('Lemešany', 524743, 1969, '21%-30%', 21),
    ('Lesíček', 524751, 430, '61%-70%', 61),
    ('Malý Slivník', 524832, 852, '71%-80%', 71),
    ('Medzany', 556823, 878, '1%-10%', 1),
    ('Mirkovce', 524883, 1344, '61%-70%', 61),
    ('Petrovany', 525014, 1963, '21%-30%', 21),
    ('Prešov', 524140, 85748, '1%-10%', 1),
    ('Rokycany', 525111, 1096, '81%-90%', 81),
    ('Ruská Nová Ves', 525138, 1241, '21%-30%', 21),
    ('Svinia', 525171, 2285, '61%-70%', 61),
    ('Terňa', 525294, 1287, '21%-30%', 21),
    ('Tuhrina', 525332, 495, '51%-60%', 51),
    ('Varhaňovce', 525383, 1456, '71%-80%', 71),
    ('Veľký Šariš', 525405, 6279, '11%-20%', 11),
    ('Víťaz', 525413, 2027, '11%-20%', 11),
    ('Červenica', 524301, 776, '71%-80%', 71),
    ('Šarišská Poruba', 525189, 620, '41%-50%', 41),
    ('Šarišská Trstená', 525197, 368, '31%-40%', 31),
    ('Šindliar', 525251, 547, '21%-30%', 21),
    ('Žehňa', 525499, 1221, '61%-70%', 61)
) AS v(obec_name, obec_kod, population, roma_share_band, roma_share_band_low)
JOIN skolske_obvody.municipalities m ON m.name = v.obec_name;

-- Public view: only municipalities above the CONFIGURED threshold, real data
-- throughout (no is_demo column — this table never carries demo rows).
-- assigned_district_id/name resolve through the VZN shared-catchment view
-- only (see comment above) — NULL is a true "not assigned in this dataset",
-- not a query failure.
DROP VIEW IF EXISTS public.so_atlas_roma_municipalities;
CREATE VIEW public.so_atlas_roma_municipalities AS
SELECT
    a.municipality_id,
    m.name                          AS municipality_name,
    a.okres,
    a.kraj,
    a.population,
    a.roma_share_band,
    a.roma_share_band_low,
    a.atlas_year,
    a.source_name,
    a.source_url,
    a.downloaded_at,
    cfg.highlight_threshold_pct,
    public.ST_AsGeoJSON(m.geom)::jsonb AS geom_geojson,
    shared.district_id              AS assigned_district_id,
    shared.district_name            AS assigned_district_name
FROM skolske_obvody.atlas_roma_share a
JOIN skolske_obvody.municipalities m ON m.id = a.municipality_id
CROSS JOIN skolske_obvody.atlas_roma_share_config cfg
LEFT JOIN public.so_shared_municipality_areas shared ON shared.municipality_id = a.municipality_id
WHERE a.roma_share_band_low > cfg.highlight_threshold_pct;

GRANT SELECT ON public.so_atlas_roma_municipalities TO anon, authenticated, service_role;
