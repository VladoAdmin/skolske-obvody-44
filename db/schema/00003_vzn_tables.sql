-- Schema file 00003: VZN (municipal ordinance) tables
-- Depends on: 00002_core_tables.sql

CREATE TABLE IF NOT EXISTS vzns (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  municipality_id UUID NOT NULL REFERENCES municipalities(id),
  reference       TEXT NOT NULL,      -- e.g. 'VZN 1/2023'
  title           TEXT,
  effective_date  DATE,
  url             TEXT,
  raw_text        TEXT,
  -- Scraping metadata
  hash            TEXT,               -- SHA-256 of raw_text for change detection
  scraped_at      TIMESTAMPTZ,
  scrape_status   TEXT NOT NULL DEFAULT 'pending'
                    CHECK (scrape_status IN ('pending', 'ok', 'error', 'changed')),
  -- Parsing status
  parse_status    TEXT NOT NULL DEFAULT 'pending'
                    CHECK (parse_status IN ('pending', 'parsed', 'manual_review', 'failed')),
  parsed_at       TIMESTAMPTZ,
  parsed_by       TEXT,               -- 'auto' | 'manual:username'
  -- Provenance
  dataset_id      UUID REFERENCES datasets(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (municipality_id, reference)
);

CREATE INDEX IF NOT EXISTS vzns_municipality_id_idx ON vzns(municipality_id);

-- Add FK from districts → vzns (cross-reference after vzns table exists)
ALTER TABLE districts
  ADD CONSTRAINT fk_districts_vzn
  FOREIGN KEY (vzn_id) REFERENCES vzns(id)
  DEFERRABLE INITIALLY DEFERRED;
