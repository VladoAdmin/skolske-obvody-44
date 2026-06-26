### Reálne blokery voči PRD v3

1. **Migrácia nedodáva PRD kontrakt 7 views**
   - PRD vyžaduje 7 views vrátane `provenance_source_allowlist` alebo ekvivalentného SQL riešenia + `host_in_allowlist()`.
   - PLAN namiesto toho vytvára/grantuje `condition_labels` ako **table**, nie view.
   - AC 1 hovorí „7 views + function“; PLAN má fakticky 6 dátových views + tabuľku.
   - Navyše `GRANT SELECT ON skolske_obvody.condition_labels TO anon` porušuje hard rule: **anon SELECT iba na nové views, nie tabuľky**.

2. **`condition_labels` tabuľka v exposed schéme je kontraktový/security mismatch**
   - PRD zakazuje anon prístup k tabuľkám v schéme; aj keď nejde o raw PII tabuľku, PLAN explicitne grantuje tabuľku.
   - Riešenie: spraviť `condition_labels` ako view/CTE, alebo nepovrchovať samostatne vôbec.

3. **Chýba povinné riešenie `slug`/`kod_obce` pred migráciou**
   - PRD §5.1: Sonnet musí overiť, či `municipalities.slug` existuje; ak nie, migrácia musí pridať generated `slug` alebo použiť `kod_obce`.
   - PLAN všetky views stavia na `WHERE slug='presov'`, ale nemá fallback. Ak DB nemá `slug`, migrácia spadne.

4. **SQL composition pravidlá v PLAN sú pravdepodobne nesprávny port `engine/compose.py`**
   - PRD: source of truth je `engine/compose.py`.
   - PLAN vkladá vlastné pravidlá:
     - text tvrdí RED len pri `fail` + severity high/critical v Š1–Š3, ale SQL severity vôbec nepoužíva a dá RED na akýkoľvek Š fail.
     - ORANGE dáva pri `incomplete` v akomkoľvek condition, nie len podľa rozsahu z PRD/engine.
   - Áno, PLAN píše „ak fixture nesedí, uprav“, ale zároveň dáva Sonnetu chybný implementačný kontrakt. Toto je vysoké riziko failu AC 2.

5. **Composition parity test je nerealizovateľný podľa navrhnutých fixtures**
   - `composition.json` syntetické prípady nemajú `district_id` ani seed do DB.
   - Test má robiť `SELECT composition_color FROM district_compositions WHERE district_id = ?`, ale pre syntetické cases nie je čo queryovať.
   - PRD vyžaduje 22 prípadov porovnať voči SQL view; PLAN nešpecifikuje vloženie syntetických district/verdict záznamov do test schémy.

6. **Test schéma vs aplikácia: E2E seed nepoužiteľný**
   - PLAN seeduje `skolske_obvody_test`, ale aplikácia aj Supabase client hardcodujú `db.schema = 'skolske_obvody'`.
   - E2E potom neuvidí seedované dáta.
   - Treba env prepínač schema name pre testy alebo seedovať staging `skolske_obvody` izolovanú DB, nie inú schému.

7. **Unit testy vkladajú fixtures cez nesprávny kanál**
   - PLAN pri sanitization/allowlist testoch píše „vloží fixture“, ale zároveň aplikácia používa anon key a PRD zakazuje user-facing write.
   - Ak sa to robí cez anon REST, má to správne zlyhať. Ak cez prod/staging raw DB bez izolácie, je to nebezpečné.
   - Musí byť jasne: test seed iba cez `psql $STAGING_DATABASE_URL` do izolovanej test DB/schémy alebo dedicated RPC, nie cez anon klienta.

8. **`districts/[id]` empty-state porušuje PRD**
   - PRD: ak `district_scorecard` empty → zobraziť header obvodu + alert „Engine zatiaľ nehodnotil tento obvod“.
   - PLAN: `if (!rows.length) notFound()`.
   - To je funkčný contract mismatch; obvod bez verdictov nemá byť 404.

9. **`districts/[id]` header nemá dáta pre PRD požiadavky**
   - PRD vyžaduje názov obvodu + link `/municipalities/<muni_id>` + ref na VZN ak je.
   - PLAN `district_scorecard` contract neobsahuje `municipality_id`, `municipality_name`, ani VZN dáta/fetch.
   - Frontend ich teda nevie splniť.

10. **Disclaimer banner nespĺňa povinný text ani verzie**
    - PRD vyžaduje konkrétny text vrátane `methodology_version` a `engine_version`.
    - PLAN komponent má skrátený statický text s `...` a nefetchuje `engine_metadata`.
    - Tiež PRD uvádza `localStorage dismiss_disclaimer_session`, PLAN používa `sessionStorage`.

11. **MDX page bez Next configu môže rozbiť build**
    - PLAN pridáva `app/o-metodike/page.mdx` a inštaluje MDX balíky, ale nespomína update `next.config.*` pre MDX.
    - Pri štandardnom Next 14 projekte `.mdx` route bez konfigurácie neprejde buildom.

12. **`@supabase/ssr` dependency nie je v install kroku**
    - PLAN používa `createServerClient` z `@supabase/ssr`, ale inštaluje iba leaflet a MDX.
    - Ak scaffold nemá `@supabase/ssr`, build spadne. PRD spomína `@supabase/supabase-js`, nie automaticky `@supabase/ssr`.

13. **Scope-isolation test je špecifikovaný nefunkčne**
    - PLAN chce assertovať `municipality_id != Prešov UUID` na všetkých 6 views.
    - Nie všetky views majú `municipality_id` podľa PLAN/PRD (`engine_metadata`, `findings_public`, `district_scorecard` v PLAN).
    - Test bude buď nekompilovať, alebo nebude overovať reálny leak.

14. **Pre-flight cesty sú nekonzistentné s repo layoutom**
    - PLAN používa `git -C projects/skolske-obvody-44`, ale potom `test -s tests/fixtures/composition.json` bez prefixu alebo `cd`.
    - To môže generovať fixtures mimo projektu alebo failnúť podľa aktuálneho working directory.

### Minimálne zmeny pred schválením

- Nahradiť `condition_labels` tabuľku view/CTE riešením; dodať presne 7 views podľa PRD, vrátane allowlist view alebo explicitne zdokumentovaného SQL ekvivalentu bez anon table grantu.
- Implementovať `slug`/`kod_obce` fallback v migrácii.
- Odstrániť ručne vymyslené composition pravidlá z PLAN alebo ich označiť len ako placeholder; záväzne portovať `engine/compose.py`.
- Opraviť parity fixtures: každý syntetický case musí mať seeded `district_id` a verdicts v test DB.
- Zjednotiť test schema/app schema.
- Opraviť `/districts/[id]` empty state a doplniť fetch dát pre municipality link/VZN.
- Doplniť disclaimer metadata fetch a presný text.
- Doplniť MDX config a `@supabase/ssr` dependency alebo použiť iba `@supabase/supabase-js`.

VERDICT: BLOCK — PLAN porušuje DB kontrakt PRD (`7 views`, no anon table grants), má nefunkčnú testovaciu schému/fixtures a nesplní povinné district/disclaimer správanie.
