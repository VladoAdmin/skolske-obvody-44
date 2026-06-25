### Kontrola opráv v1 blockerov

- **`condition_labels` ako table / anon grant:** čiastočne opravené — tabuľka aj grant zmizli. Ale vznikol nový kontraktový problém: `district_scorecard` už nevystavuje `condition_label_sk` ani `condition_order`, hoci PRD ich vyžaduje vo view.
- **7 views + allowlist:** prevažne opravené — plán má 7. view `provenance_allowed_hosts` + `host_in_allowlist()`.
- **`slug` fallback:** nie je spoľahlivo opravený — ak existuje `kod_obce`, generated `slug = lower(kod_obce)`, takže `slug='presov'` nikdy nevznikne a sanity check/migrácia spadne.
- **Composition port cez `compose.py`:** smerovo opravené — už nie placeholder pravidlá, ale workflow ešte nemá úplne realizovateľné fixture mapovanie na `district_id`.
- **Test schema vs app schema:** opravené v §5.1, ale znovu rozbité v §11 defaultom na `skolske_obvody_test`.
- **Anon write v testoch:** opravené — write ide cez `psql`.
- **District empty state:** opravené — už nie `notFound()` pri prázdnom scorecarde.
- **District header dáta:** čiastočne opravené, ale fallback z `district_map_features` stále nemá `municipality_name` ani VZN.
- **Disclaimer:** opravené — localStorage + verzie z `engine_metadata`.
- **MDX config:** opravené.
- **`@supabase/ssr`:** opravené — dependency pridaná.

### Zostávajúce reálne blokery

1. **Slug fallback je funkčne chybný**
   - Ak DB nemá `municipalities.slug`, ale má `kod_obce`, plán vytvorí `slug = lower(kod_obce)`.
   - Potom views používajú `slug='presov'` / `LIKE '%presov%'`, čo na číselnom kóde neprejde.
   - Výsledok: migrácia môže spadnúť aj pri validnej Prešov municipality.

2. **Migrácia/test seed poradie je nefunkčné na čistej staging DB**
   - §5.1 spúšťa:
     1. `0001_init.sql`
     2. `0010_sprint_c_read_views.sql`
     3. `seed_sprint_c.sql`
   - Ale `0010` má sanity check, ktorý vyžaduje existujúci Prešov záznam.
   - Na prázdnej DB pred seedom teda migrácia spadne.

3. **`district_scorecard` porušuje PRD dátový kontrakt**
   - PRD vyžaduje vo view `condition_label_sk` a `condition_order`.
   - PLAN v2 ich presúva do frontend TS mapy.
   - To síce môže renderovať UI, ale nesplní DB read-layer kontrakt ani query contract PRD.

4. **Scope-isolation test stále nesedí na view kontrakty**
   - PLAN chce v testoch assertovať `municipality_id` v:
     - `district_compositions` — view ho podľa kontraktu nemá.
     - `findings_public` — view ho podľa kontraktu tiež nemá.
   - Testy buď zlyhajú typovo/runtime, alebo nebudú reálne overovať leak.

5. **Composition fixtures stále nie sú jednoznačne queryovateľné**
   - `dump_composition_fixtures.py` output neobsahuje `district_id`.
   - Test má robiť `WHERE district_id = ?`, ale fixture JSON podľa plánu poskytuje len `name/verdicts/expected/actual`.
   - Seed síce tvrdí, že existuje 22 districtov, ale chýba deterministické mapovanie fixture → seeded UUID.

6. **Test schema rozhodnutie je kontradiktórne**
   - §5.1 správne hovorí: staging používa rovnakú schému `skolske_obvody`.
   - §11 default pri nereagovaní Vlada hovorí: seed do `skolske_obvody_test`.
   - Aplikácia má hardcoded `db.schema = 'skolske_obvody'`, takže E2E seed v `_test` schéme neuvidí.

7. **Supabase exposed schema nie je reálne overená**
   - PRD vyžaduje potvrdiť, že `skolske_obvody` je v exposed schemas, inak `BLOCKERS.md`.
   - PLAN kontroluje iba existenciu namespace v Postgrese, nie PostgREST/Supabase API exposure.
   - REST môže failovať aj pri úspešnej SQL migrácii.

VERDICT: BLOCK — PLAN v2 odstránil väčšinu v1 problémov, ale stále má nefunkčný slug fallback, rozbitý staging/test flow a porušuje DB kontrakt `district_scorecard`/scope testov.
