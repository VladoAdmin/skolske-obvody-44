## Kritická revízia PRD — Sprint C Frontend Skelet

Tento PRD má dobrý produktový zámer, ale ako implementačný kontrakt je momentálne príliš deravý. Obsahuje viacero blokujúcich rozporov medzi cieľom, out-of-scope, dátovým kontraktom a akceptačnými kritériami. Najväčší problém: Sprint C sa tvári ako read-only frontend, ale zároveň povoľuje/má vytvárať DB migrácie, RLS politiky, možný DB view/generate column a dokonca port engine logiky do frontendu. To už nie je “skelet UI”, ale zásah do dátovej a metodickej vrstvy.

---

## Blokujúce problémy

### 1. Rozpor: “read-only frontend” vs. DB migrácie / RLS zmeny

V §1 je jasný hard non-goal:

> “Sprint C nemení engine, nepočíta nové verdikty, nepridáva auth, nepýta od používateľa zápis. Iba číta z DB.”

Ale §5.1 hovorí:

> “Sprint C nesmie pridať nové RLS politiky. Predpokladá… Ak chýba, BLOCKER — Sprint C vytvorí migráciu `0001_sprint_c_read_policies.sql` s `GRANT SELECT` + RLS `USING (true)`…”

Toto je interný kontraktový bug. PRD naraz zakazuje a prikazuje pridávať RLS politiky. Navyše `USING (true)` pre verejné tabuľky s nálezmi, dôkazmi, provenance URL a možno textami z rozhodnutí je bezpečnostné rozhodnutie, nie frontend detail.

**Požadovaná zmena:** Rozhodnúť jednoznačne:
- buď Sprint C je striktne read-only a pri chýbajúcom RLS sa blokuje bez migrácie,
- alebo Sprint C zahŕňa DB bezpečnostnú migráciu, ktorá musí byť explicitne súčasťou scope, reviewovaná a schválená.

Aktuálny stav je BLOCKER.

---

### 2. CSV export je súčasne požiadavka aj out-of-scope

V §2 use-case:

> “Novinár / úradník | Otvorí `/findings`, filtruje severity=high, exportuje CSV”

Ale §8 explicitne hovorí:

> “CSV/PDF export findings” je out of scope.

A §3.5 export vôbec nešpecifikuje.

Toto je čistý scope conflict. Implementátor nevie, či CSV export má robiť alebo nie. Testy ani akceptačné kritériá ho nespomínajú.

**Požadovaná zmena:** Buď vyhodiť export z use-case, alebo ho presunúť do funkčných požiadaviek a akceptačných kritérií.

---

### 3. Neplatný / nerealistický Supabase REST kontrakt pre geometriu

V §5.2 je query:

```ts
geom_json:geom::text
school:schools(id, name, geom_json:geom::text)
```

Toto je veľmi pravdepodobne neplatné pre PostgREST/Supabase `.select()` syntax. PostgREST bežne nepodporuje ľubovoľné SQL casty ani `ST_AsGeoJSON()` priamo v select stringu týmto spôsobom. V §7 sa potom píše:

> “`ST_AsGeoJSON(geom)::json` v select; alternatívne views…”

To tiež nie je bežný Supabase REST pattern. Ak je `geom` PostGIS geometry, frontend bez DB view/RPC nemusí dostať použiteľný GeoJSON.

**Požadovaná zmena:** Definovať reálny kontrakt:
- ideálne DB view `districts_geojson`, `schools_geojson`, prípadne `district_map_features`,
- alebo RPC `get_district_map_features()`,
- presné JSON shape: `FeatureCollection` vs raw geometry,
- SRID a coordinate order,
- null/error handling.

Bez toho je mapa kriticky riziková.

---

### 4. Kompozičná farba sa má počítať vo frontende portom engine logiky — to je architektonicky zlé

§5.2:

> “frontend ho vypočíta v TS portom `engine/compose.py` na strane servera…”

To priamo odporuje §1:

> “Sprint C nemení engine, nepočíta nové verdikty…”

Aj keď sa to nazve “kompozičná farba”, stále ide o aplikačnú/metodickú rozhodovaciu logiku. Navyše PRD neobsahuje presné pravidlá kompozície, takže frontend tím ich má odvodzovať z Pythonu. To je drift magnet.

§7 síce hovorí:

> “Unit test porovná TS port vs engine Python referenčné výstupy…”

Ale nie je jasné, ako sa Python engine spustí v Next/Vitest pipeline, kde sú referenčné fixtures, či budú versionované a čo sa stane pri zmene engine verzie.

**Požadovaná zmena:** Pre compliance demo musí byť composition výsledok súčasťou dátového produktu engine:
- buď uložený v tabuľke/view `district_compositions`,
- alebo materializovaný v `verdicts`/`districts`,
- s `methodology_version` a `engine_version`.

Frontend nemá portovať právno-metodickú logiku z Pythonu.

---

### 5. Dátové kontrakty sú neúplné pre väčšinu stránok

§5 definuje iba čiastočný query pattern pre `districts`. Ale stránky vyžadujú oveľa viac:

- §3.1 footer: `dataset_version`, `methodology_version`, `engine_version`, `MAX(verdicts.computed_at)` — nie je definované, z ktorej tabuľky sa berú prvé tri hodnoty.
- §3.2 KPI: počet verdiktov, open findings — nie sú definované status enumy, severity enumy, query shape.
- §3.4 scorecard: `value`, `confidence`, `completeness`, `state`, `evidence_text`, `provenance.source`, `provenance.fetched_at`, `is_illustrative`, `is_proxy`, `is_mock` — nie je definované, či sú to stĺpce, JSONB polia, nested relations alebo názvy v DB.
- §3.5 findings: `municipality`, `district`, `condition_code`, `status`, `created_at` — nie je definovaná join cesta ani FK.
- §3.6 municipalities agregácie — nie je definované, či sa počítajú client-side, server-side, viewom alebo joinom.

Toto nie je dostatočný API contract. Implementátor bude hádať DB schému.

**Požadovaná zmena:** Doplniť minimálne:
- tabuľka → stĺpce → typy → nullable,
- enum hodnoty a ordering,
- joiny/FK názvy,
- príklady odpovedí,
- fallback správanie pri null/empty.

---

### 6. Verejný anon prístup k findings/evidence/provenance nie je dátovo ani právne ošetrený

§1 definuje verejné demo pre ministerstvo, úradníkov, novinárov. §5.1 povoľuje anon read na `findings`, `verdicts`, `districts`, `schools`, `municipalities`.

Ale PRD nerieši:
- či `evidence_text` neobsahuje osobné údaje alebo citlivé formulácie,
- či `provenance.source` URL nemôžu ukazovať na interné alebo nestabilné zdroje,
- či findings môžu poškodzovať reputáciu obcí/škôl pri “čiastočných dátach”,
- aké disclaimery musia byť v UI.

§1 síce hovorí:

> “nie obhájiť, že každý obvod má reálne pravidelné porušenie”

Ale to nie je prenesené do konkrétnych UI požiadaviek okrem metodickej stránky.

**Požadovaná zmena:** Pridať povinný disclaimer na Domov, Mapu, Detail obvodu a Findings. Tiež definovať redakčné pravidlá pre `evidence_text` a verejné publikovanie findings.

---

## Vysoké riziká a nejasnosti

### 7. `/regions` tabuľka je použitá, ale nie je v RLS ani dátovom kontrakte

§3.3:

> “Hranice PSK z `regions` tabuľky, ak je, inak fallback bbox”

Ale §5.1 RLS zoznam obsahuje iba:

> `districts`, `schools`, `verdicts`, `findings`, `municipalities`

`regions` chýba. Ak má byť použitá, musí mať kontrakt aj read policy. Ak je fallback bbox, treba definovať presný bbox.

---

### 8. `PRESOV_ID` je nedefinované magické ID

§5.2:

```ts
.eq('municipality_id', PRESOV_ID)
```

Nie je definované, odkiaľ `PRESOV_ID` pochádza. Hardcode DB UUID/id v aplikácii je krehký. Lepší kontrakt je `municipality.slug = 'presov'`, `kod_obce`, alebo config env.

---

### 9. OSM tiles bez attribution / usage policy

§3.3 a §4 hovoria Leaflet + OSM tiles. Chýba:
- povinná OSM attribution,
- tile provider limit,
- fallback pri blokovaní,
- či Vercel preview/demo traffic neporuší OSM Tile Usage Policy.

Pre verejné demo pre novinárov/ministerstvo by som nepovažoval priamy public OSM tile endpoint za dostatočne robustný bez explicitného posúdenia.

---

### 10. Akceptačné kritériá sú čiastočne nedeterministické alebo netestovateľné

#### §6.2:
> “12 vyfarbenými polygónmi (žiadny grey-only stav)”

Ale §7 zároveň hovorí:

> “Engine ešte nevyplnil composition… UI gracefully zobrazí ‘nezhodnotené’ s šedou farbou”

Ak je šedá povolená fallback farba, nemôže byť akceptačné kritérium “žiadny grey-only stav” bez presnej definície, koľko grey je povolených. Ak má byť 12 farebných, DB musí garantovať 12 complete compositions.

#### §6.3:
> “Lesnícka č. 1 … aspoň 7 vyplnenými 5-tuple hodnotami”

Nie je jasné, čo znamená “vyplnená” hodnota, keď `INCOMPLETE` je tiež validný `value`. Tiež nie je jasné, ako sa stabilne nájde obvod podľa názvu — presný názov, diakritika, school vs district?

#### §6.4:
> “link funkčný”

Externé URL môžu byť dočasne nedostupné, blokovať botov alebo vracať 403. Testovať HTTP funkčnosť externých zdrojov v E2E je flaky. Stačí validné `href`, `target`, prípadne link rendering.

#### §6.6:
> “GPT-5.5 verify final = APPROVE…”

To nie je technické akceptačné kritérium produktu. Je to procesná meta-podmienka a navyše viazaná na konkrétny model. Nemala by byť v PRD ako runtime acceptance.

---

### 11. Playwright E2E nie je špecifikované, ako získa validné `/districts/[id]`

§4:

> “Playwright E2E na 4 hlavné cesty: `/`, `/map`, `/districts/[id]`, `/findings`”

Ale neexistuje fixture ani stabilné ID. Ak sa má test spoliehať na živú Supabase DB, bude krehký. Ak nemajú byť mocky (§4: “žiadne mocky”), treba aspoň seedované staging dáta alebo query pred testom.

---

### 12. “Žiadne mocky” je prakticky v konflikte s testovateľnosťou a CI

§4:

> “Data fetch … žiadne mocky”

To je OK pre preview/demo, ale pre unit/E2E testy potrebujete buď:
- stabilnú test DB,
- snapshot fixtures,
- alebo network mocking.

PRD to nevysvetľuje. Ak testy bežia proti reálnej preview DB, budú flaky a závislé na Supabase/RLS/network stave.

---

### 13. Performance ciele nemajú metodiku merania

§4:

> “LCP < 2.5s na preview; mapa lazy-loaded; iniciálny JS < 200 KB gzip okrem leaflet”

Chýba:
- nástroj merania,
- device/network profile,
- či sa meria `/`, `/map` alebo oboje,
- ako sa počíta “okrem leaflet” v Next bundle analyzer,
- či preview Vercel cold start sa ráta.

Bez metodiky je to neoveriteľné.

---

### 14. A11y pre mapu je nedostatočne špecifikované

§4:

> “shadcn/ui defaults … kontrast min AA”

Mapa je kritický UI prvok, ale chýba:
- keyboard navigácia k obvodom,
- alternatívna tabuľka/list pre mapové dáta,
- non-color encoding pre RED/ORANGE/GREEN,
- screen reader labels pre polygóny,
- focus state pri výbere obvodu.

Pre verejné demo štátnej témy je toto slabé.

---

### 15. Triedenie severity nie je definované

§3.5:

> “Sort: by severity → created_at desc default”

Chýba severity order. Napr. `critical > high > medium > low > info`? Ale PRD spomína iba `high` a `info`. Treba definovať enum a poradie.

---

### 16. Branch a projektová metadata sú podozrivé

Header:

> `Branch: feat/sprint-1-ingest`

Pre Sprint C frontend skelet je branch `feat/sprint-1-ingest` minimálne mätúci. Môže signalizovať, že sa bude pracovať v nesprávnej vetve alebo miešať ingest/frontend zmeny.

---

## Chýbajúce požiadavky

### 17. Error/empty/loading states

Nie je špecifikované, čo sa zobrazí pri:
- Supabase error,
- RLS 401/403,
- prázdnych verdicts,
- chýbajúcej geometrii,
- chýbajúcej škole,
- chýbajúcom `provenance`,
- partial load mapy.

Pre demo pred klientom sú tieto stavy kritické.

---

### 18. URL routing a selection state

§3.3 hovorí:

> “pravý postranný panel alebo route `/districts/[id]`”

To je scope ambiguity. “Alebo” nie je implementačný kontrakt. Treba rozhodnúť:
- klik naviguje na detail,
- alebo ostáva na mape s panelom,
- alebo panel aj deep-link route.

---

### 19. Export findings chýba, ak má byť use-case splnený

Ako vyššie: ak novinár má exportovať CSV, treba definovať:
- export všetkých filtrovaných výsledkov alebo aktuálnej stránky,
- encoding UTF-8 BOM?,
- názvy stĺpcov,
- či evidence_text plný alebo truncated,
- bezpečnostné disclaimery.

Ak nie, odstrániť z PRD.

---

### 20. Pagination pre findings tabuľku

§3.5 hovorí “všetkých findings”. Aj keď dnes môže byť málo dát, register nálezov prirodzene narastie. Chýba pagination alebo server-side limit. Public anon query bez limitu je zlý pattern.

---

### 21. Map geometry size / simplification

Nie je definované, či MultiPolygon geometrie sú zjednodušené. Ak sú detailné, initial map payload môže byť veľký a performance cieľ padne. Treba mať view s `ST_SimplifyPreserveTopology` alebo aspoň veľkostný limit.

---

### 22. Verzionovanie metodiky a engine

PRD opakovane používa `methodology_version`, `engine_version`, `dataset_version`, ale nedefinuje:
- tabuľku,
- hodnotu,
- fallback,
- zodpovednosť,
- či sa majú zhodovať naprieč verdicts.

Pre compliance demo je verzionovanie kľúčové. Nemôže byť dekorácia vo footeri bez zdroja pravdy.

---

## Odporúčané zmeny pred implementáciou

1. **Rozhodnúť scope DB zmien.** Buď striktne read-only frontend, alebo explicitne zahrnúť DB views/RLS migrations.
2. **Zrušiť TS port engine kompozície.** Composition musí byť v DB ako output engine/view.
3. **Dodať reálne DB kontrakty.** Pre `districts`, `schools`, `verdicts`, `findings`, `municipalities`, prípadne `regions`.
4. **Vyriešiť GeoJSON cez view/RPC.** Nepoužívať neoverený `geom::text` select.
5. **Odstrániť alebo implementovať CSV export.** Teraz je v rozpore.
6. **Definovať disclaimery a dátovú bezpečnosť.** Najmä pre public anon findings/evidence.
7. **Spresniť akceptačné kritériá.** Stabilné test dáta, deterministic IDs, netestovať externé URL uptime.
8. **Doplniť empty/error/loading states.**
9. **Definovať severity/status/value enumy.**
10. **Definovať performance/a11y meranie a map fallback.**

---

VERDICT: BLOCK — PRD má blokujúce rozpory v scope a bezpečnosti (§1 vs §5.1, §2 vs §8), neplatný/neurčitý Supabase/PostGIS kontrakt (§5.2) a presúva engine metodickú logiku do frontendu bez špecifikácie pravidiel.
