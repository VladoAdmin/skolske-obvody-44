# PRD v2 — Sprint C: Frontend Skelet + DB read-layer (PSK § 44 compliance demo)

**Status:** draft v3 po 2× GPT-5.5 gate (v1 = BLOCK, v2 = BLOCK; reviews v `PRD_review.md`, `PRD_review_v2.md`)
**Author:** F2 (Opus 4.8) on cc-pipeline-v2
**Created:** 2026-06-25
**Project:** `projects/skolske-obvody-44`
**Branch:** `feat/sprint-c-frontend` (vytvoríme z `feat/sprint-1-ingest`; nemiešame s ingest sprintami)

---

## 1. Cieľ a kontext

Engine (Sprint A, commit `f860a09`) vypočítal pre **12 Prešovských školských obvodov** v 9 podmienkach (Š1–Š3, P-a–P-f) 5-tuple verdikt + semafor kompozíciu (RED/ORANGE/GREEN). Výsledky sú v `skolske_obvody.verdicts` + `findings`.

**Sprint C postaví:**

1. **Read DB-layer** — SQL views/RPC + (ak treba) RLS politiky + composition column, tak aby frontend mohol jednoduchou Supabase REST query dostať GeoJSON-friendly dáta a hotovú kompozičnú farbu. (Read-only zápis: žiadne nové RLS, ktoré by povolili zápis pre anon; nová `GRANT SELECT` na `anon` rolu IBA pre nové views, nie tabuľky.)
2. **Verejné read-only demo UI** — mapa PSK, scorecard, register nálezov, drill-down dôkaz s disclaimerom.

**Klientske publikum:** ministerstvo školstva, PSK úradníci, novinári.

**Hard non-goal:**
- Žiadny user-facing zápis/write.
- Žiadny anon prístup k tabuľkám (`schools`, `districts`, `verdicts`, `findings`, `municipalities`) priamo — iba cez views.
- Žiadny port metodickej (composition) logiky do frontendu.
- Žiadne nové data ingest, žiadne ML, žiadny auth.

---

## 2. Scope — explicitný delivery zoznam

### 2.1 DB-layer (in scope)

**Hard rule:** Všetky public views sú SQL-scoped na Prešov cez `WHERE municipality_id = (SELECT id FROM municipalities WHERE slug = 'presov')`. Frontend filter `.eq(...)` nie je bezpečnostná hranica — je len UX optimalizácia.

Nová migrácia `db/migrations/0010_sprint_c_read_views.sql` (7 views, idempotentná pre `CREATE OR REPLACE VIEW`):

1. `district_compositions` VIEW: per district aktuálny `composition_color` (`RED|ORANGE|GREEN|NONE`), `composition_reason`, `composition_details JSONB`, `engine_version`, `methodology_version`, `computed_at`. **Logika = SQL port `compose_color()` z `engine/compose.py`.** Sonnet implementuje ako CASE/aggregate; Haiku porovná output s Python referenčným fixture-dump pre 22 prípadov.  *(VIEW nie MATERIALIZED — runner ho neviem refreshovať bez ďalšieho hooku; ak v budúcnosti pôjdeme na MV, migrácia bude samostatná.)*
2. `district_map_features` VIEW: `id, name, municipality_id, school_id, geometry_confidence, composition_color, composition_reason, geom_geojson JSONB` (cez `ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.0001))::jsonb`), `school_geom_geojson JSONB, school_name`.
3. `district_scorecard` VIEW: per `(district_id, condition_code)` najnovší verdict (DISTINCT ON computed_at DESC) + meta join: `condition_label_sk, condition_order SMALLINT, methodology_rule, methodology_version, provenance_source TEXT, provenance_fetched_at TIMESTAMPTZ, evidence_public_text TEXT, is_illustrative, is_proxy, is_mock, value, confidence, data_completeness, composition_color` (z `district_compositions`). **`evidence_public_text` = sanitizovaná verzia `evidence_text`** (truncated 500 znakov, regex-strip emailov + tel. čísel + rodných čísel) — viď §5.5.
4. `municipalities_summary` VIEW: `name, districts_count, schools_count, open_findings_count, red_districts_count, orange_districts_count, green_districts_count, none_districts_count`. **Scope-limited** — vidno len Prešov.
5. `findings_public` VIEW: findings + join district.name, municipality.name, `condition_label_sk`, severity, `severity_rank SMALLINT` (5/4/3/2/1), status, `evidence_public_text` (truncated 200, sanitizovaný — viď §5.5), created_at, `district_id`. **Scope-limited** — len findings pre Prešovské obvody.
6. `engine_metadata` VIEW: aktuálny `dataset_version, methodology_version, engine_version` (MAX z `verdicts`), `MAX(computed_at) AS last_engine_run_at`, `verdicts_count BIGINT, districts_count BIGINT, schools_count BIGINT, open_findings_count BIGINT`. **Scope-limited** na Prešov.
7. `provenance_source_allowlist` VIEW (alebo statický `lib/config/provenance-allowlist.ts` — Sonnet vyberie podľa toho, či logika musí byť v SQL). Allowed hosts: `slov-lex.sk, cvti.sk, osm.org, openstreetmap.org, geoportal.gov.sk, presov.sk, gov.sk, statistics.sk, atlasromskychkomunit.sk, minedu.sk, mzv.sk`. Sonnet **vo views replacuje `provenance_source` na NULL ak host nie je v allowliste**; frontend hide URL v takom prípade.

**Grants:**
- `GRANT USAGE ON SCHEMA skolske_obvody TO anon;`
- `GRANT SELECT ON skolske_obvody.{view1..view7} TO anon;`
- **Žiadny GRANT na tabuľky.** Anon nesmie čítať raw `verdicts`, `findings`, `schools`, `districts`, `municipalities` priamo.
- Supabase exposed schemas: Sprint C **predpokladá**, že `skolske_obvody` je v `db.api.schemas` (config Supabase). Migrácia pridá `COMMENT ON SCHEMA skolske_obvody IS 'public read-views only';` ako dokumentačný marker. Ak Supabase nemá schému exposed, Sonnet pridá note do `BLOCKERS.md` a navrhne config zmenu cez Vlada.

### 2.2 Frontend (in scope)
- Stránky: `/`, `/map`, `/districts/[id]`, `/findings`, `/municipalities`, `/o-metodike`.
- Komponenty: `app-shell`, `region-map` (leaflet), `district-scorecard`, `findings-table`, `verdict-row`, `provenance-badge`, `disclaimer-banner`, `engine-footer`.
- Disclaimer-banner: viditeľný na všetkých stránkach (`/`, `/map`, `/findings`, `/districts/[id]`). Text v §3.7.

### 2.3 Out of scope (explicitne)
- CSV / PDF / Excel export (akýkoľvek).
- Auth, admin, write API.
- Geocoding adresy žiaka.
- Iné obce ako Prešov.
- Smart vyhľadávanie / ML.
- Print stylesheet.

---

## 3. Funkčné požiadavky (detailné)

### 3.1 Disclaimer (povinný banner)
**Text:** „Toto demo zobrazuje analytické výstupy nad čiastočnými verejnými dátami pre 12 školských obvodov mesta Prešov. **Nie je oficiálnym výkladom súladu s §44 zákona č. 596/2003.** Hodnoty `INCOMPLETE` / `INSUFFICIENT_DATA` znamenajú **dátovú medzeru**, nie nesúlad. Verzia metodiky: `<methodology_version>`. Verzia enginu: `<engine_version>`."

Komponent `disclaimer-banner`, sticky pod headerom, zatvárateľný per session (localStorage `dismiss_disclaimer_session`), ale **na `/districts/[id]` vždy znova zobrazený** (kvôli vážnosti drill-down dát).

### 3.2 Stránka `/` (Domov)
- 200–400 slov úvod o § 44 a o demo.
- 3 KPI karty z `engine_metadata` + agregát z `municipalities_summary`:
  - „Posúdených obvodov" = `SUM(districts_count)` (12).
  - „Spracovaných podmienok" = `count(verdicts.id)`.
  - „Otvorených nálezov" = `SUM(open_findings_count)`.
- CTA „Otvoriť mapu PSK" → `/map`.

### 3.3 Stránka `/map`
- Mapa Leaflet + OSM tile provider **s povinnou attribution** (`'&copy; OpenStreetMap contributors'`). Default zoom + center: PSK bbox z `lib/config/region.ts`.
- Načítanie `district_map_features` (jeden REST call, ≤ 12 features, simplified geometry). Vyfarbenie podľa `composition_color`:
  - `GREEN` → `#16a34a`, fill 30 %
  - `ORANGE` → `#f97316`, fill 30 %
  - `RED` → `#dc2626`, fill 30 %
  - `NONE` (engine ho nezhodnotil) → `#9ca3af`, fill 15 %, **+ ikona `?` (non-color a11y encoding)**
- Markery škôl: ak `school_geom_geojson` ≠ NULL → pin s `school_name`.
- Hover na polygón: tooltip názov + farba + (ak NONE) reason.
- Klik na polygón: **navigácia na `/districts/[id]`** (deep-link; žiadny side panel — rozhodnuté jednoznačne).
- A11y: pod mapou tabuľka „Zoznam obvodov" (link `/districts/[id]`, stĺpec semafor + non-color symbol ✓/~/✕/?) — keyboard navigovateľná. Mapa má `role="application"` + `aria-label`.

### 3.4 Stránka `/districts/[id]`
- Identifikácia: `[id]` je `districts.id` UUID. Linky vždy generujeme z dát, nehardcodujeme.
- Header: názov obvodu + odkaz `/municipalities/<muni_id>` + ref na VZN (z `vzns` tabuľky ak je).
- Disclaimer banner (vždy zobrazený).
- Scorecard: čítané z `district_scorecard`, **zoradené podľa `condition_order ASC`** (S1=1, S2=2, S3=3, Pa=4 … Pf=9). Per riadok:
  - kód podmienky, ľudský label (SK) — z view stĺpca `condition_label_sk`.
  - `value` (badge), `confidence` (0–1 progress), `data_completeness` (0–1 progress), kompozit semafor (✓/~/✕/?).
  - status flags badge (`is_illustrative`, `is_proxy`, `is_mock`).
  - „Dôkaz" collapse → `evidence_public_text` (sanitizovaný v DB view) + odkaz na `provenance_source`. **Ak `provenance_source` je NULL** (host nie v allowliste), odkaz sa nezobrazí, namiesto neho text „Zdroj nie je verejne publikovateľný". Linky: `rel="noopener noreferrer nofollow"`, `target="_blank"`.
- Pod scorecard mini-mapa (leaflet, ssr:false) s týmto obvodom + školou.
- Empty stav: ak žiadne verdicts → „Engine zatiaľ nehodnotil. Posledný engine run: `<engine_metadata.computed_at>`".

### 3.5 Stránka `/findings`
- Server Component číta `findings_public` cez REST s pagination 50/page (`?from=&to=`).
- URL search params: `severity`, `status`, `condition`, `page`. Filter UI updatuje search params (preserved deep-link).
- Tabuľka: severity badge, municipality, district, condition_code, `evidence_public_text` (už sanitizovaný + truncovaný na 200 v DB; žiadny tooltip s raw obsahom), status badge, created_at (rel. čas).
- Severity poradie (zoradenie + filter sort): `critical > high > medium > low > info`.
- Klik na riadok → `/districts/[id]`.
- Empty: „Žiadne nálezy pre tieto filtre."
- Loading: skeleton rows.
- Error: alert s retry tlačidlom.

### 3.6 Stránka `/municipalities`
- Z `municipalities_summary` (1 riadok = Prešov). Stĺpce: name, districts_count, schools_count, red/orange/green counts, open_findings_count, link na `/municipalities/[id]`.
- `/municipalities/[id]`: zoznam obvodov (link na `/districts/[id]`) + mini-mapa.

### 3.7 Stránka `/o-metodike`
- MDX statický obsah: §44, 9 podmienok, semaforová kompozícia (popíšeme jasne), GAP-y (Register adries, OSM low-confidence geom).
- Link na GitHub repo + `engine_version` z `engine_metadata`.

---

## 4. Nefunkčné požiadavky

| Aspekt | Cieľ |
|---|---|
| Stack | Next.js 14 App Router (existujúci scaffold) + TypeScript strict + Tailwind + shadcn/ui |
| Map lib | `react-leaflet@4` + `leaflet@1.9`. Component s `dynamic(..., {ssr:false})` wrapperom. |
| Data fetch | Server Components + `@supabase/supabase-js` (anon key). Žiadny user-facing write. |
| Build | `npm run build` MUSÍ prejsť |
| Lint | `npm run lint` strict, no `any` |
| Type-check | `tsc --noEmit` zelený |
| Unit tests | Vitest. Composition SQL view porovnaný s Python `compose_color` cez **fixtures dump** (`tests/fixtures/composition.json` vygenerovaný z `engine/compose.py` pre 12 prešovských districtov + ďalšie syntetické edge cases). |
| E2E tests | Playwright. **Seed:** test runner pred E2E načíta `tests/fixtures/seed_sprint_c.sql` do staging Supabase schémy `skolske_obvody_test` (alebo použije RPC `seed_sprint_c_test()` ak je staging k dispozícii). Ak staging nie je dostupný v CI, E2E sa preskakuje so značkou `SKIPPED:no-staging-db` (nie failuje), ale lokálne pred deploy musí prejsť. |
| Performance | LCP < 2.5s na `/` na Vercel preview (meranie: Lighthouse mobile preset, „Slow 4G", emulated). Map page nemá target LCP (lazy-loaded chunky). Initial JS na `/` < 200 KB gzip (bez leaflet). Bundle reporting: `npx next build` `.next/analyze`. |
| A11y | WCAG AA kontrast, non-color encoding semaforu (✓/~/✕/?), keyboard nav cez Tab pre mapu (mapa fallback tabuľka). Mapa má `aria-describedby` na pod-tabuľku. |
| i18n | SK only |
| Mobile | Tablet+mobile responsive; mapa touch zoom |
| OSM attribution | Vždy zobrazená v ľavom dolnom rohu mapy. Tile provider podľa OSM Tile Usage Policy = OK na demo (< 10k req/deň). |

---

## 5. Dátové kontrakty (Supabase REST)

### 5.1 Region geometry
PSK bbox je **konštanta v `lib/config/region.ts`**:
```ts
export const PSK_BBOX: [number, number, number, number] = [20.4, 48.3, 22.8, 49.7] // minLon, minLat, maxLon, maxLat
export const PSK_CENTER: [number, number] = [49.0, 21.6]
export const PSK_DEFAULT_ZOOM = 9
export const PRESOV_MUNICIPALITY_SLUG = 'presov' // FK: municipalities.slug = 'presov'
```
**Identifikácia Prešova:** Sonnet pred zostavením kódu over, či `municipalities` má stĺpec `slug` alebo `kod_obce`. Ak nemá `slug`, migrácia `0010_sprint_c_read_views.sql` pridá `slug TEXT GENERATED ALWAYS AS (kod_obce) STORED` (alebo lookup cez `kod_obce`). Žiadne hardcoded UUID v aplikácii.

### 5.2 Query patterns

Všetky views sú v DB scope-limited na Prešov (§2.1 hard rule). Frontend filter `.eq('municipality_slug', ...)` nie je potrebný a NESMIE byť jediná bezpečnostná hranica.

```ts
// /map — vráti len 12 Prešovských obvodov bez ďalšieho filtra
supabase.schema('skolske_obvody')
  .from('district_map_features')
  .select('*')

// /districts/[id] — selektor je UUID
supabase.schema('skolske_obvody')
  .from('district_scorecard')
  .select('*')
  .eq('district_id', id)
  .order('condition_order', { ascending: true })

// /findings — pagination + filter
supabase.schema('skolske_obvody')
  .from('findings_public')
  .select('*', { count: 'exact' })
  .order('severity_rank', { ascending: false })
  .order('created_at', { ascending: false })
  .range(from, to)
```

**Stĺpec `severity_rank`** vo view: `CASE severity WHEN 'critical' THEN 5 WHEN 'high' THEN 4 WHEN 'medium' THEN 3 WHEN 'low' THEN 2 ELSE 1 END`.

### 5.3 Enums (canonical)
- `verdicts.value`: `pass | fail | incomplete | risk | low_data | signal | no_signal | not_evaluated` (z DB migrácie 0001).
- `findings.severity`: `critical | high | medium | low | info`.
- `findings.status`: `open | acknowledged | resolved | wont_fix`.
- `district_compositions.composition_color`: `RED | ORANGE | GREEN | NONE`.

### 5.5 Public sanitization rules (povinné v DB views)

| Pole | Transformácia v SQL |
|---|---|
| `evidence_public_text` v `findings_public` | `LEFT(regexp_replace(regexp_replace(regexp_replace(evidence_text, '[\w\.-]+@[\w\.-]+', '[email]', 'g'), '\+?\d{2,4}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3}', '[tel]', 'g'), '\d{6}/\d{3,4}', '[rč]', 'g'), 200)` |
| `evidence_public_text` v `district_scorecard` | rovnaký regex, `LEFT(..., 500)` |
| `provenance_source` v `district_scorecard` a `findings_public` | `CASE WHEN host_in_allowlist(provenance_source) THEN provenance_source ELSE NULL END` cez SQL funkciu `host_in_allowlist(text) RETURNS boolean` definovanú v migrácii |
| Žiadne PII stĺpce (adresy žiakov, RČ, mená) | views ich nevystavujú vôbec |

`host_in_allowlist(url)` funkcia: parsuje hostname (regex `^https?://([^/:]+)`), porovnáva voči konštantnému CTE / array allowlistu. Kapitálne písmená case-insensitive.

### 5.6 Empty / Error semantics
| Scenár | UI |
|---|---|
| `district_map_features` empty | Mapa zobrazí PSK hranicu + alert „Engine ešte nebežal nad týmto územím" |
| `district_scorecard` empty | Header obvodu + alert „Engine zatiaľ nehodnotil tento obvod" |
| `findings_public` empty + žiadne filtre | „Engine zatiaľ nevygeneroval žiadny nález" |
| `findings_public` empty + s filtrami | „Žiadne nálezy pre tieto filtre" |
| Supabase 4xx/5xx | Alert s message + retry button + sentry log |

---

## 6. Akceptačné kritériá (deterministické)

1. **Migrácia** `0010_sprint_c_read_views.sql` aplikovateľná idempotentne (`psql ... -f` 2× rovnaký výsledok). Vytvorí **7 views + `host_in_allowlist()` funkciu + `GRANT USAGE ON SCHEMA + GRANT SELECT` na views (nie tabuľky)**.
1b. **Scope test (anon):** REST call na **všetkých 6 dátových views** — `district_map_features`, `district_scorecard`, `findings_public`, `municipalities_summary`, `district_compositions`, `engine_metadata` — vráti iba Prešovské záznamy / agregáty. Žiadny `municipality_id ≠ Prešov` nesmie uniknúť. Verifikované Vitestom proti staging Supabase (alebo lokálne psql + JWT s anon role).
1c. **Sanitization test:** fixture verdict s emailom + tel. číslom + RČ v `evidence_text` → **OBE** `findings_public.evidence_public_text` aj `district_scorecard.evidence_public_text` MUSIA obsahovať `[email]`, `[tel]`, `[rč]` a NESMÚ obsahovať pôvodné hodnoty. SQL fixture + assert.
1d. **Allowlist test:** fixture verdict s `provenance.source = 'http://internal.local/secret'` → **OBE** `district_scorecard.provenance_source` aj `findings_public.provenance_source` = NULL. Fixture s `https://slov-lex.sk/...` → vráti pôvodnú URL v oboch.
2. **Composition parita:** Sonnet test `tests/composition.test.ts` načíta `tests/fixtures/composition.json` (generovaný `engine/compose.py` pre 12 prešovských districtov + 10 syntetických edge cases) → `SELECT composition_color FROM district_compositions WHERE district_id IN (...)` MUSÍ vrátiť identické hodnoty pre všetkých 22.
3. **Build:** `npm run build` zelený. `npm run lint` zelený. `tsc --noEmit` zelený.
4. **Unit tests:** Vitest ≥ 8 testov, všetky zelené (composition parita + scorecard formatter + severity sort + map feature transform + url params parser + provenance link sanitizer + empty-state predicate + disclaimer dismiss logic).
5. **E2E lokálne** (Playwright proti reálnemu staging Supabase): 4 scenáre — `/`, `/map`, `/districts/<seed UUID>`, `/findings` — všetky zelené. Test berie district UUID z `tests/fixtures/seed_sprint_c.sql`, nie z naming.
6. **Vercel preview** otvorí `/map` a zobrazí ≥ 1 farebný polygón (nie všetky NONE). Screenshot `/map` 1280×720 čitateľný.
7. **Screenshot `/districts/<id>`** 1280×720 ukáže scorecard so všetkými 9 podmienkami + disclaimer banner.
8. *(presunuté mimo produktových AC — pipeline procesná podmienka)* GPT-5.5 final verify = `APPROVE` / `APPROVE_WITH_CHANGES`, max 2 re-iterácie, viď §10.
9. **OSM attribution** prítomné na mape (text „© OpenStreetMap contributors").
10. **Disclaimer banner** prítomný na `/`, `/map`, `/findings`, `/districts/[id]` — overené Playwrightom.

---

## 7. Riziká + mitigácie

| Riziko | Mitigácia |
|---|---|
| Composition SQL ≠ Python compose | Fixture-driven parita test (22 prípadov) v CI |
| `ST_AsGeoJSON` veľký payload | `ST_SimplifyPreserveTopology(0.0001)` v view |
| `react-leaflet` SSR | `dynamic(..., {ssr:false})` wrapper |
| Vercel env vars chýbajú | PLAN explicit zoznam, Sonnet pred deploy spustí `vercel env ls` |
| Staging Supabase nie je k dispozícii | E2E lokálne podmienka, CI skip s značkou |
| OSM tile usage policy | Demo limit < 10k req/deň → OK; ak Vlado škáluje, prepneme na MapTiler/Stadia |
| Anon read leak citlivých dát | Views vystavujú iba safe stĺpce (`findings_public` truncuje evidence_text, žiadne PII); audit v review |
| GPT verify BLOCK | Max 2 re-iterácie; potom Vlado decision |

---

## 8. Open questions pre PLAN stage

1. Materialized view vs view pre `district_compositions` — rozhodnuté: VIEW (žiadny refresh hook).
2. `findings_public.evidence_text` truncation — rozhodnuté: v DB (`evidence_public_text` view stĺpec).
3. Sentry / logging — out of scope; zachová sa Next error boundary so správou „nahláste správcovi".
4. `provenance_source_allowlist` ako view vs config v TS — PLAN rozhodne; SQL allowlist funkcia je povinná, TS allowlist je voliteľná redundantná obrana.

## 10. Pipeline procesná podmienka (mimo produktových AC)

Sprint C beží na `cc-pipeline-v2`. GPT-5.5 verify v stage 7 musí vrátiť `APPROVE` alebo `APPROVE_WITH_CHANGES`. `BLOCK` triggeruje max 2 re-iterácie; pri 3. `BLOCK` Sprint C zastavuje a F2 reportuje Vladovi s root cause. Toto je governance pipeline, nezasahuje do produktovej akceptácie.
