-- STEP 2 — clean canonical address set derived from the authoritative
-- City-of-Prešov register (skolske_obvody.register_adries, 16307 rows).
--
-- Additive only: a new table + public read view. The raw register table and
-- the legal Š1–Š3 verdict views are untouched.
--
-- Clean rules (all applied by ingest/build_register_adries_clean.py):
--   * keep only habitable      (obyvatelna = TRUE)
--   * keep only NOT withdrawn   (vyradena   = FALSE)
--   * normalise the street name with the SAME normalisation the geometry build
--     uses (lower + unaccent + strip leading "Ulica " + drop "č."/dots +
--     expand "Arm. gen." + collapse whitespace) -> column ulica_norm
--   * trim súpisné / orientačné číslo (btrim)
--   * drop exact duplicates on (ulica_norm, supisne_cislo, orientacne_cislo)
--
-- ulica keeps a representative ORIGINAL spelling; ulica_norm is the join key
-- to vzn_street_ranges (normalised) used by Step 3.

CREATE TABLE IF NOT EXISTS skolske_obvody.register_adries_clean (
  id               BIGSERIAL PRIMARY KEY,
  register_id      BIGINT,                 -- source register_adries.id (one representative row per dup group)
  mesto            TEXT,
  cast_mesta       TEXT,
  ulica            TEXT,                   -- representative original spelling
  ulica_norm       TEXT NOT NULL,          -- normalised street (VZN join key)
  supisne_cislo    TEXT,
  orientacne_cislo TEXT,
  adresa           TEXT,
  psc              TEXT,
  mestska_oblast   TEXT
);

CREATE INDEX IF NOT EXISTS register_adries_clean_norm_idx
  ON skolske_obvody.register_adries_clean (ulica_norm);

-- Public read view (PostgREST does not expose the skolske_obvody schema).
CREATE OR REPLACE VIEW public.so_register_adries_clean AS
SELECT
  id,
  register_id,
  mesto,
  cast_mesta,
  ulica,
  ulica_norm,
  supisne_cislo,
  orientacne_cislo,
  adresa,
  psc,
  mestska_oblast
FROM skolske_obvody.register_adries_clean;

GRANT SELECT ON public.so_register_adries_clean TO anon;
