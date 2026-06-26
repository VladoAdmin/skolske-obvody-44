## Revízia PRD v2 — Sprint C Frontend Skelet + DB read-layer

V2 významne zlepšuje kontrakt oproti v1. Väčšina pôvodných blockerov je adresovaná, ale zostávajú 2 reálne blokery v oblasti public anon dátového prístupu a bezpečnosti publikovaných dôkazov.

---

## Overenie v1 blockerov

### 1. Read-only frontend vs DB migrácie/RLS  
**Adresované čiastočne.**  
PRD už explicitne hovorí, že Sprint C zahŕňa DB read-layer, views a `GRANT SELECT` iba na views. Rozpor z v1 je teda odstránený.

**Zostáva problém:** views s `GRANT SELECT TO anon` sú verejný API povrch. PRD sa stále spolieha na frontend filter `.eq('municipality_slug', 'presov')`, čo nie je bezpečnostná hranica.

---

### 2. CSV export scope conflict  
**Adresované.**  
CSV/PDF/Excel export je jednoznačne out of scope a nie je v use-case/funkčných požiadavkách.

---

### 3. Supabase/PostGIS GeoJSON kontrakt  
**Adresované.**  
`district_map_features` cez `ST_AsGeoJSON(... )::jsonb` je reálny kontrakt. Shape je dostatočne špecifikovaný pre frontend.

---

### 4. Composition logika vo frontende  
**Adresované dostatočne pre Sprint C.**  
Frontend už neportuje engine logiku. SQL view `district_compositions` je stále duplicita metodickej logiky, ale je v DB read-layeri, verzionovaná a testovaná fixture paritou. Nie je to blocker, hoci dlhodobo by composition mala byť engine output.

---

### 5. Neúplné dátové kontrakty  
**Výrazne zlepšené, ale ešte sú menšie medzery.**  
Views a REST query patterns sú použiteľné. Zostávajú neblokujúce nepresnosti:
- `/` KPI „Spracovaných podmienok = count(verdicts.id)` nemá definovaný public view field. Pridať napr. `engine_metadata.verdicts_count`.
- `district_scorecard.order('condition_code')` negarantuje fixné poradie `S1,S2,S3,Pa...`; treba `condition_order`.
- počet views je nejasný: §2.1 vymenúva 6–7 podľa `region_psk`, AC hovorí 6.

---

### 6. Verejný anon prístup k findings/evidence/provenance  
**Nie je dostatočne adresované — zostáva blocker.**  
Disclaimer pribudol a `findings_public.evidence_text` je truncovaný, ale:
- `district_scorecard` stále publikuje plný `evidence_text`;
- `provenance_source` ide verejne bez URL allowlistu/sanitizácie;
- neexistuje akceptačné kritérium pre PII/redakčný audit;
- anon views môžu potenciálne vystaviť viac než 12 Prešovských obvodov.

---

## Zostávajúce blokery

### BLOCKER 1 — Verejné views nie sú hard-scopeované na Prešov

PRD hovorí, že iné obce ako Prešov sú out of scope, ale public views:

- `district_map_features`
- `district_scorecard`
- `municipalities_summary`
- `findings_public`

nie sú špecifikované ako hard-filtered na `municipality_slug = 'presov'`.

Frontend query:

```ts
.eq('municipality_slug', 'presov')
```

nie je bezpečnostné opatrenie. Anon používateľ môže volať Supabase REST priamo bez filtra.

**Požadovaná zmena:**
- Každý public view musí mať v SQL pevný filter na Prešov, napr. cez join na `municipalities.slug = 'presov'` alebo `kod_obce`.
- Alebo musí PRD explicitne povedať, že verejne publikovaný scope je celý dataset, a doplniť právny/dátový audit pre celý dataset.
- Query filter vo frontende nesmie byť jediná ochrana scope.

---

### BLOCKER 2 — Public evidence/provenance sanitizácia je nedostatočná

`findings_public` truncuje `evidence_text`, ale `district_scorecard` ukazuje plný `evidence_text` v collapsible „Dôkaz“. To obchádza mitigáciu uvedenú pri findings.

Pre verejné demo pre ministerstvo/novinárov je potrebné explicitne garantovať, že dôkazové texty a URL sú public-safe.

**Požadovaná zmena:**
- Namiesto raw `evidence_text` vystaviť vo views iba `evidence_public_text`, sanitizovaný/truncovaný/redigovaný.
- Definovať URL allowlist alebo minimálne validáciu `provenance_source` na `http/https`, bez interných hostov, bez `localhost`, bez privátnych IP.
- Pridať acceptance check: public views neobsahujú PII/sensitive text podľa definovaných pravidiel.
- Ak má byť full evidence dostupný, musí byť explicitne schválený ako public-safe dátový produkt.

---

## Ne blokujúce zmeny pred implementáciou

1. Doplniť `engine_metadata.verdicts_count`, aby home KPI nečítalo tabuľku `verdicts`.
2. Pridať `condition_order` do `district_scorecard`.
3. Zjednotiť počet views v AC: 6 vs 7 podľa `region_psk`.
4. Rozhodnúť `VIEW` vs `MATERIALIZED VIEW`; `CREATE OR REPLACE` neplatí pre materialized view.
5. Odstrániť alebo presunúť „GPT-5.5 final verify“ mimo produktových AC; aj keď je označené ako pipeline podmienka, stále je v AC sekcii.
6. Explicitne uviesť `GRANT USAGE ON SCHEMA skolske_obvody TO anon` / Supabase exposed schema predpoklad, ak ešte nie je garantovaný infra setupom.

VERDICT: BLOCK — V2 odstránila hlavné scope rozpory, ale public anon views stále nemajú hard dátový scope na Prešov a publikovanie evidence/provenance nie je bezpečnostne/redakčne uzavreté.
