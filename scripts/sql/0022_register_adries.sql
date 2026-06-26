-- Register adries a stavieb — authoritative City-of-Prešov address register.
-- Source: ingest/data/register_adries_presov.json (16307 records, 401 streets).
-- NO coordinates in this register (geocoding is a separate budgeted step).
-- Ingested by ingest/ingest_register_adries.py via f2_exec_sql.

CREATE TABLE IF NOT EXISTS skolske_obvody.register_adries (
  id               BIGSERIAL PRIMARY KEY,
  mesto            TEXT,
  cast_mesta       TEXT,
  ulica            TEXT,
  supisne_cislo    TEXT,
  orientacne_cislo TEXT,
  adresa           TEXT,
  psc              TEXT,
  obyvatelna       BOOLEAN,
  vyradena         BOOLEAN,
  mestska_oblast   TEXT,
  popis            TEXT,
  index_domu       TEXT,
  raw              JSONB
  -- NOTE: index_domu is NOT unique in the source register (11 duplicate keys
  -- + 5 blank), so it cannot serve as a conflict key. The loader does a clean
  -- full reload (TRUNCATE + INSERT) keyed on the synthetic id PK.
);

CREATE INDEX IF NOT EXISTS register_adries_ulica_idx
  ON skolske_obvody.register_adries (ulica);
CREATE INDEX IF NOT EXISTS register_adries_obyvatelna_idx
  ON skolske_obvody.register_adries (obyvatelna);

-- Public read view (PostgREST does not expose the skolske_obvody schema).
CREATE OR REPLACE VIEW public.so_register_adries AS
SELECT
  id,
  mesto,
  cast_mesta,
  ulica,
  supisne_cislo,
  orientacne_cislo,
  adresa,
  psc,
  obyvatelna,
  vyradena,
  mestska_oblast,
  popis,
  index_domu
FROM skolske_obvody.register_adries;

GRANT SELECT ON public.so_register_adries TO anon;
