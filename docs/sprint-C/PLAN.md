# PLAN — Sprint C: Frontend Skelet + DB read-layer

**Status:** draft v3 po 2× GPT-5.5 gate (v1, v2 = BLOCK; reviews `PLAN_review.md`, `PLAN_review_v2.md`)
**Author:** F2 (Opus 4.8)
**Based on:** `PRD.md` v3 (APPROVE_WITH_CHANGES)
**Stack:** Next.js 14 App Router + TypeScript strict + Tailwind + shadcn/ui + @supabase/supabase-js + react-leaflet@4
**Pipeline:** cc-pipeline-v2 (Sonnet code, Haiku tests, GPT-5.5 verify)

---

## 0. Pred-flight gates (Sonnet musí splniť pred kódom)

Všetky príkazy bežia z `projects/skolske-obvody-44/` (Sonnet `cd` raz na začiatok).

```bash
cd projects/skolske-obvody-44

# 1. branch sanity
git checkout -b feat/sprint-c-frontend feat/sprint-1-ingest

# 2. supabase env (prod + staging)
test -n "$NEXT_PUBLIC_SUPABASE_URL" || fail "missing NEXT_PUBLIC_SUPABASE_URL"
test -n "$NEXT_PUBLIC_SUPABASE_ANON_KEY" || fail
test -n "$STAGING_DATABASE_URL" || warn "no staging DB → E2E will be skipped"

# 3. schema + slug column check
psql "$DATABASE_URL" -c "SELECT 1 FROM pg_namespace WHERE nspname='skolske_obvody';" | grep -q 1 || fail "schema missing"

# 4. read compose.py (NOT placeholder — port verne v migrácii §2.3)
cat engine/compose.py

# 5. composition fixtures
test -s tests/fixtures/composition.json || python3 scripts/dump_composition_fixtures.py > tests/fixtures/composition.json

# 6. node deps
test -d node_modules || npm ci
```

Ak ktorýkoľvek krok zlyhá → BLOCKER do `docs/sprint-C/BLOCKERS.md` → F2 alert Vladovi.

---

## 1. Architektúra

### 1.1 Repo layout (po skončení sprintu)

```
projects/skolske-obvody-44/
├── db/migrations/0010_sprint_c_read_views.sql     (NEW — DB views + sanitization + grants)
├── scripts/dump_composition_fixtures.py            (NEW — Python: vyextrahuje compose_color() vstup+výstup pre 22 prípadov do JSON)
├── app/
│   ├── layout.tsx                                  (UPDATE — disclaimer banner mount + footer)
│   ├── page.tsx                                    (UPDATE — KPI karty + úvod)
│   ├── map/page.tsx                                (UPDATE — full map page)
│   ├── findings/page.tsx                           (UPDATE — server-side table + filters)
│   ├── municipalities/page.tsx                     (UPDATE — list)
│   ├── municipalities/[id]/page.tsx                (NEW — detail)
│   ├── districts/[id]/page.tsx                     (NEW — scorecard + drill-down)
│   ├── o-metodike/page.mdx                         (NEW — metodológia)
│   └── error.tsx, not-found.tsx, loading.tsx       (NEW — Next 14 error boundaries)
├── components/
│   ├── layout/app-shell.tsx                        (UPDATE — nav + header + footer + disclaimer)
│   ├── disclaimer-banner.tsx                       (NEW)
│   ├── engine-footer.tsx                           (NEW)
│   ├── region-map.tsx                              (NEW — dynamic ssr:false leaflet)
│   ├── region-map.client.tsx                       (NEW — actual leaflet impl, "use client")
│   ├── district-mini-map.tsx                       (NEW — single-district leaflet, ssr:false)
│   ├── district-mini-map.client.tsx                (NEW)
│   ├── district-scorecard.tsx                      (NEW — 9-row scorecard table)
│   ├── verdict-row.tsx                             (NEW — single condition row)
│   ├── provenance-link.tsx                         (NEW — handles NULL provenance gracefully)
│   ├── findings-table.tsx                          (NEW)
│   ├── findings-filters.tsx                        (NEW — URL search params)
│   ├── kpi-card.tsx                                (NEW)
│   └── ui/*                                        (shadcn primitives — install on demand: badge, button, table, alert, dialog, dropdown-menu, select, skeleton, progress, separator, sheet)
├── lib/
│   ├── supabase/server.ts                          (UPDATE — server client)
│   ├── supabase/types.ts                           (NEW — generované typy pre 6 views — manuálne, lebo gen z views je flaky)
│   ├── config/region.ts                            (NEW — PSK bbox/center/zoom + provenance allowlist mirror)
│   ├── compliance/colors.ts                        (NEW — semafor → tailwind class mapping)
│   ├── compliance/labels.ts                        (NEW — condition_code → SK label fallback ak view chýba)
│   ├── format/severity.ts                          (NEW — severity → badge variant + non-color symbol)
│   └── format/dates.ts                             (NEW — rel time)
└── tests/
    ├── fixtures/composition.json                   (NEW — 22 prípadov compose_color)
    ├── fixtures/seed_sprint_c.sql                  (NEW — seed pre E2E)
    ├── unit/composition-parity.test.ts             (NEW)
    ├── unit/scope-isolation.test.ts                (NEW — anon nevidí non-Prešov)
    ├── unit/sanitization.test.ts                   (NEW — email/tel/RČ regex strip)
    ├── unit/allowlist.test.ts                      (NEW — provenance host filter)
    ├── unit/severity-sort.test.ts                  (NEW)
    ├── unit/url-params.test.ts                     (NEW)
    ├── unit/provenance-link.test.ts                (NEW)
    ├── unit/disclaimer-dismiss.test.ts             (NEW)
    └── e2e/{home,map,district,findings}.spec.ts    (NEW)
```

### 1.2 Routing tree

```
/                         → Home (KPI + úvod)
/map                      → PSK mapa
/districts/[id]           → drill-down scorecard
/findings                 → filtrovaná tabuľka + URL params
/municipalities           → zoznam (1 záznam)
/municipalities/[id]      → municipality detail
/o-metodike               → MDX statika
```

### 1.3 Data flow (per stránka)

- Všetky page komponenty sú **Server Components**. Žiadny client fetch okrem leaflet komponentov.
- Server client: `createClient(supabaseUrl, anonKey, { schema: 'skolske_obvody', auth: { persistSession: false } })`.
- Žiadny service-role key v aplikácii, nikde.
- ISR `revalidate = 300` (5 min) na statickom obsahu (`/`, `/o-metodike`); `revalidate = 60` na ostatných (engine môže meniť dáta).

---

## 2. SQL migrácia `0010_sprint_c_read_views.sql` (Sonnet implementuje)

Striktný kontrakt. Sonnet **MUSÍ** vytvoriť **7 views** + 2 funkcie. ŽIADNY `GRANT SELECT` na tabuľky.

### 2.0 Slug column (povinný prvý blok migrácie)

Migrácia pridá nullable `slug TEXT` (nie generated, lebo source pre Prešov je vždy 'presov' bez ohľadu na kod_obce) a explicit UPDATE pre Prešov podľa **name match** (najspoľahlivejšie). Sanity check sa NEROBÍ v migrácii — robí ho seed/aplikácia po vložení dát.

```sql
-- Idempotent: nullable TEXT, no generated.
ALTER TABLE skolske_obvody.municipalities ADD COLUMN IF NOT EXISTS slug TEXT;

-- Set 'presov' for any row matching name (idempotent).
UPDATE skolske_obvody.municipalities
SET slug = 'presov'
WHERE slug IS NULL
  AND (lower(name) = 'prešov' OR lower(name) = 'presov' OR lower(name) = 'mesto prešov');

-- Generic fallback for other municipalities (name → slug):
UPDATE skolske_obvody.municipalities
SET slug = lower(regexp_replace(translate(name, 'áäčďéíĺľňóôŕšťúýž','aacdeillnoorstuyz'), '[^a-z0-9]+', '-', 'g'))
WHERE slug IS NULL AND name IS NOT NULL;

-- Index for performant lookups in views
CREATE INDEX IF NOT EXISTS municipalities_slug_idx ON skolske_obvody.municipalities(slug);

-- Sanity check is moved OUT of migration into runtime: if no Prešov row exists yet,
-- views still create cleanly (`presov_id` will be NULL and views return empty rows).
-- Seed assertions in seed_sprint_c.sql verify slug='presov' exists.
```

### 2.1 `host_in_allowlist(text)` funkcia

```sql
CREATE OR REPLACE FUNCTION skolske_obvody.host_in_allowlist(url text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $$
  WITH
    norm AS (
      SELECT
        CASE WHEN url IS NULL THEN NULL
             ELSE lower(regexp_replace(url, '^[Hh][Tt][Tt][Pp][Ss]?://([^/:]+).*$', '\1'))
        END AS host
    ),
    allowlist(allowed) AS (VALUES
      ('slov-lex.sk'), ('cvti.sk'), ('osm.org'), ('openstreetmap.org'),
      ('geoportal.gov.sk'), ('presov.sk'), ('gov.sk'), ('statistics.sk'),
      ('atlasromskychkomunit.sk'), ('minedu.sk'), ('mzv.sk')
    )
  SELECT EXISTS (
    SELECT 1
    FROM norm, allowlist
    WHERE norm.host IS NOT NULL
      AND (norm.host = allowlist.allowed OR norm.host LIKE ('%.' || allowlist.allowed))
  );
$$;
```
(Sonnet môže prepísať implementáciu, ale kontrakt = `boolean` + IMMUTABLE + handle subdomains + NULL + case-insensitive scheme.)

### 2.2 `sanitize_evidence(text, int)` funkcia

```sql
CREATE OR REPLACE FUNCTION skolske_obvody.sanitize_evidence(t text, max_len int)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT LEFT(
    regexp_replace(
      regexp_replace(
        regexp_replace(
          coalesce(t, ''),
          '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[email]', 'g'
        ),
        '\+?\d{2,4}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2,3}', '[tel]', 'g'
      ),
      '\d{6}\s*/\s*\d{3,4}', '[rč]', 'g'
    ),
    max_len
  );
$$;
```

### 2.3 `district_compositions` VIEW — port `engine/compose.py`

**Source of truth:** `engine/compose.py::compose_color()`. Sonnet pri implementácii NESMIE vymýšľať pravidlá — **prečíta compose.py, portuje rule-by-rule do SQL** a verifikuje fixture paritou.

Štruktúra (záväzná):
```sql
CREATE OR REPLACE VIEW skolske_obvody.district_compositions AS
WITH presov AS (SELECT id FROM skolske_obvody.municipalities WHERE slug LIKE '%presov%' LIMIT 1),
latest AS (
  SELECT DISTINCT ON (v.district_id, v.condition_code)
    v.district_id, v.condition_code, v.value, v.confidence, v.data_completeness,
    v.is_illustrative, v.is_proxy, v.is_mock,
    v.engine_version, v.methodology_version, v.computed_at
  FROM skolske_obvody.verdicts v
  JOIN skolske_obvody.districts d ON d.id = v.district_id
  WHERE d.municipality_id = (SELECT id FROM presov)
  ORDER BY v.district_id, v.condition_code, v.computed_at DESC
)
SELECT
  d.id AS district_id,
  /* Sonnet: composition_color CASE expression = 1:1 port of engine/compose.py compose_color() — verified against tests/fixtures/composition.json */
  ... AS composition_color,
  ... AS composition_reason,
  ... AS composition_details,
  ... engine_version, methodology_version, computed_at
FROM skolske_obvody.districts d
WHERE d.municipality_id = (SELECT id FROM presov);
```

**Sonnet workflow:**
1. `cat engine/compose.py` — prečítaj plné pravidlá.
2. Skopíruj rule semantics 1:1 do SQL CASE/aggregate.
3. Spusti `python3 scripts/dump_composition_fixtures.py > tests/fixtures/composition.json` (toto je VÝSTUP z compose.py — source of truth).
4. Seed fixtures do staging schémy `skolske_obvody` (rovnaká schéma, izolovaná DB cez `$STAGING_DATABASE_URL`).
5. Spusti SQL view, porovnaj výstup voči fixture JSON pre všetkých 22 prípadov.
6. Ak parity != 100 %, oprav SQL (Python = SoT). Žiadny ručne vymyslený fix.

### 2.4 Ostatné views — kontrakty (Sonnet implementuje)

Pre každý view:
- `WHERE municipality_id = (SELECT id FROM skolske_obvody.municipalities WHERE slug='presov')` v hlavnej tabuľke a transitívne v joinoch.
- Stĺpce a typy podľa `PRD.md §2.1`.

| View | Stĺpce (kľúčové) |
|---|---|
| `district_map_features` | id, name, municipality_id, school_id, geometry_confidence, composition_color, composition_reason, geom_geojson, school_geom_geojson, school_name |
| `district_scorecard` | district_id, district_name, **municipality_id, municipality_name, vzn_id, vzn_ref_url**, condition_code, **condition_label_sk** (inline CASE; PRD requires), **condition_order** (inline CASE), value, confidence, data_completeness, methodology_rule, methodology_version, provenance_source (NULL ak nie v allowliste), provenance_fetched_at, evidence_public_text (sanitize 500), is_illustrative, is_proxy, is_mock, composition_color, computed_at |
| `municipalities_summary` | municipality_id, name, districts_count, schools_count, open_findings_count, red/orange/green/none_districts_count |
| `findings_public` | finding_id, district_id, district_name, **municipality_id**, municipality_name, condition_code, condition_label_sk, severity, severity_rank, status, evidence_public_text (sanitize 200), provenance_source (allowlist), created_at |
| `engine_metadata` | dataset_version, methodology_version, engine_version, last_engine_run_at, verdicts_count, districts_count, schools_count, open_findings_count |

**`condition_label_sk` + `condition_order` zdroj:** vystavené **inline v SQL `district_scorecard`** ako CASE výrazy (PRD §2.1 ich vyžaduje vo view). **Frontend** má **redundantnú** mapu v `lib/compliance/labels.ts` ako fallback/typescript safety net. SQL CASE príklad:

```sql
-- v SELECT district_scorecard:
CASE v.condition_code
  WHEN 'S1' THEN 'Š1 — Adresy žiakov a obvod'
  WHEN 'S2' THEN 'Š2 — Topologické pokrytie'
  WHEN 'S3' THEN 'Š3 — Kompozícia obvodu'
  WHEN 'Pa' THEN 'P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km'
  WHEN 'Pb' THEN 'P-b — Pešia trasa'
  WHEN 'Pc' THEN 'P-c — MHD dostupnosť'
  WHEN 'Pd' THEN 'P-d — Bariéry (cesty, koľaje)'
  WHEN 'Pe' THEN 'P-e — Sociálny kontext (Atlas MRK)'
  WHEN 'Pf' THEN 'P-f — Demografia detí'
END AS condition_label_sk,
CASE v.condition_code
  WHEN 'S1' THEN 1 WHEN 'S2' THEN 2 WHEN 'S3' THEN 3
  WHEN 'Pa' THEN 4 WHEN 'Pb' THEN 5 WHEN 'Pc' THEN 6
  WHEN 'Pd' THEN 7 WHEN 'Pe' THEN 8 WHEN 'Pf' THEN 9
END AS condition_order,
```

Frontend `lib/compliance/labels.ts` constant (parita s SQL):

```ts
// lib/compliance/labels.ts
export const CONDITION_LABELS_SK: Record<string,{label:string; order:number}> = {
  S1: { label: 'Š1 — Adresy žiakov a obvod', order: 1 },
  S2: { label: 'Š2 — Topologické pokrytie', order: 2 },
  S3: { label: 'Š3 — Kompozícia obvodu', order: 3 },
  Pa: { label: 'P-a — Vzdialenosť ZŠ 1. stupeň ≤ 2 km', order: 4 },
  Pb: { label: 'P-b — Pešia trasa', order: 5 },
  Pc: { label: 'P-c — MHD dostupnosť', order: 6 },
  Pd: { label: 'P-d — Bariéry (cesty, koľaje)', order: 7 },
  Pe: { label: 'P-e — Sociálny kontext (Atlas MRK)', order: 8 },
  Pf: { label: 'P-f — Demografia detí', order: 9 },
}
```

DB `district_scorecard` vystavuje `condition_code` **aj** `condition_label_sk` aj `condition_order` cez inline CASE (§2.4 tabuľka). Frontend constant je **redundantná safety net**. Sort vo `findings` a scorecard preferuje `condition_order` z view (server-side `.order('condition_order')`); ak view ho z akéhokoľvek dôvodu nevracia (napr. zmena kontraktu), padá na TS map fallback.

### 2.5 GRANTs (povinné v migrácii — posledný blok)

**7 views**: `district_compositions`, `district_map_features`, `district_scorecard`, `municipalities_summary`, `findings_public`, `engine_metadata`, `provenance_allowed_view` (= jednoduchý placeholder view exponujúci allowlist hostov, voliteľne, kvôli kontraktu „7 views" v PRD — implementácia: `SELECT unnest(ARRAY[...]) AS host`).

```sql
GRANT USAGE ON SCHEMA skolske_obvody TO anon;
GRANT SELECT ON
  skolske_obvody.district_compositions,
  skolske_obvody.district_map_features,
  skolske_obvody.district_scorecard,
  skolske_obvody.municipalities_summary,
  skolske_obvody.findings_public,
  skolske_obvody.engine_metadata,
  skolske_obvody.provenance_allowed_hosts
TO anon;
-- NO grants on raw tables. NO grants on tables in this schema for anon role.
-- Explicit defensive REVOKE for raw tables (idempotent):
REVOKE ALL ON skolske_obvody.districts FROM anon;
REVOKE ALL ON skolske_obvody.schools FROM anon;
REVOKE ALL ON skolske_obvody.verdicts FROM anon;
REVOKE ALL ON skolske_obvody.findings FROM anon;
REVOKE ALL ON skolske_obvody.municipalities FROM anon;
COMMENT ON SCHEMA skolske_obvody IS 'public read-views only — anon must NOT access raw tables';
```

**Anon raw-table leak negative test** (po migrácii, pred dalsím krokom):
```bash
# expect 401/403 or empty
curl -fsS -H "apikey: $NEXT_PUBLIC_SUPABASE_ANON_KEY" -H "Accept-Profile: skolske_obvody" \
  "$NEXT_PUBLIC_SUPABASE_URL/rest/v1/verdicts?select=*" \
  && fail "anon CAN read raw verdicts table — REVOKE failed"
```

### 2.6 Idempotencia

Migrácia začína blokom:
```sql
DROP VIEW IF EXISTS skolske_obvody.district_compositions CASCADE;
DROP VIEW IF EXISTS skolske_obvody.district_map_features CASCADE;
DROP VIEW IF EXISTS skolske_obvody.district_scorecard CASCADE;
DROP VIEW IF EXISTS skolske_obvody.municipalities_summary CASCADE;
DROP VIEW IF EXISTS skolske_obvody.findings_public CASCADE;
DROP VIEW IF EXISTS skolske_obvody.engine_metadata CASCADE;
DROP VIEW IF EXISTS skolske_obvody.provenance_allowed_hosts CASCADE;
DROP FUNCTION IF EXISTS skolske_obvody.host_in_allowlist(text);
DROP FUNCTION IF EXISTS skolske_obvody.sanitize_evidence(text, int);
```
Žiadny `condition_labels` TABLE — bol odstránený z PLAN v2.

---

## 3. Composition fixture dump (Sonnet)

Každý fixture case má **deterministický UUID**, aby seed do staging DB + frontend test mohli dohodnúť rovnaké riadky.

```python
# scripts/dump_composition_fixtures.py
import json, sys, uuid
sys.path.insert(0, 'projects/skolske-obvody-44')
from engine.compose import compose_color
from engine.constants import CONDITION_CODES

NAMESPACE = uuid.UUID('00000000-0000-0000-0000-000000000001')  # constant

# 12 real Prešov districts (UUIDs vytiahnuté z prod DB SELECT id, name FROM districts WHERE municipality...)
REAL_DISTRICTS = []  # Sonnet vyplní cez psql query, do JSON ako [{district_id, name, verdicts_dict}, ...]

# 10 syntetických edge cases (deterministic UUIDs via uuid5(NAMESPACE, name))
SYNTHETIC = [
  ("synth_all_pass",       {c:"pass" for c in CONDITION_CODES}),
  ("synth_s1_fail",        {**{c:"pass" for c in CONDITION_CODES}, "S1":"fail"}),
  ("synth_s2_incomplete",  {**{c:"pass" for c in CONDITION_CODES}, "S2":"incomplete"}),
  ("synth_pa_fail",        {**{c:"pass" for c in CONDITION_CODES}, "Pa":"fail"}),
  ("synth_pc_risk",        {**{c:"pass" for c in CONDITION_CODES}, "Pc":"risk"}),
  ("synth_empty",          {}),
  # 4 more — Sonnet adds based on compose.py branches
]

out = []
for d in REAL_DISTRICTS:
  result = compose_color({k: {"value": v} for k,v in d["verdicts"].items()})
  out.append({"district_id": d["district_id"], "kind": "real", "name": d["name"],
              "verdicts": d["verdicts"], "expected": result["color"]})

for name, verdicts in SYNTHETIC:
  uid = str(uuid.uuid5(NAMESPACE, name))
  result = compose_color({k: {"value": v} for k,v in verdicts.items()})
  out.append({"district_id": uid, "kind": "synthetic", "name": name,
              "verdicts": verdicts, "expected": result["color"]})

print(json.dumps(out, indent=2, ensure_ascii=False))
```

`tests/fixtures/seed_sprint_c.sql` musí pre každý `district_id` vytvoriť odpovedajúci `districts` row + relevantné `verdicts` row-y v staging DB. Sonnet vytvorí ako sprievodný skript `scripts/render_seed_sprint_c.py` ktorý prečíta `composition.json` a vyrenderuje SQL `INSERT` riadky deterministicky.

---

## 4. Frontend implementation (Sonnet)

### 4.1 Inštalácie

```bash
# (working dir = projects/skolske-obvody-44/)
npm install react-leaflet@4 leaflet@1.9 @types/leaflet@1.9
npm install @supabase/ssr        # required for createServerClient in Server Components
npm install @next/mdx @mdx-js/loader @mdx-js/react
npx shadcn@latest add badge button table alert dialog dropdown-menu select skeleton progress separator sheet card breadcrumb
```

### 4.1.1 MDX konfigurácia (povinné pred buildom)

`next.config.mjs` musí byť rozšírený o MDX plugin, inak `app/o-metodike/page.mdx` build zlyhá:

```js
import createMDX from '@next/mdx'
const withMDX = createMDX({ extension: /\.mdx?$/ })
const nextConfig = {
  pageExtensions: ['ts', 'tsx', 'js', 'jsx', 'md', 'mdx'],
  // …existing options
}
export default withMDX(nextConfig)
```

`mdx-components.tsx` v root projektu:
```tsx
import type { MDXComponents } from 'mdx/types'
export function useMDXComponents(c: MDXComponents): MDXComponents { return { ...c } }
```

### 4.2 `lib/supabase/server.ts`

```ts
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export function createPublicClient() {
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: { get: (n) => cookies().get(n)?.value, set() {}, remove() {} },
      db: { schema: 'skolske_obvody' },
    },
  )
}
```

### 4.3 `components/region-map.tsx`

```tsx
import dynamic from 'next/dynamic'
export const RegionMap = dynamic(() => import('./region-map.client').then(m => m.RegionMapClient), { ssr: false, loading: () => <MapSkeleton/> })
```

`region-map.client.tsx`: `"use client"`, použije `MapContainer`, `TileLayer` (OSM URL + povinný attribution), `GeoJSON` pre 12 districtov, `Marker` pre školy. Click handler `useRouter().push('/districts/'+id)`.

### 4.4 `app/districts/[id]/page.tsx`

Empty-state: ak `rows.length == 0`, NEVRACIA sa 404. Stránka zobrazí header obvodu (z `districts` cez separate small fetch) + alert „Engine zatiaľ nehodnotil tento obvod".

```tsx
import { createPublicClient } from '@/lib/supabase/server'
import { DistrictScorecard } from '@/components/district-scorecard'
import { DistrictMiniMap } from '@/components/district-mini-map'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { EmptyScorecard } from '@/components/empty-scorecard'
import { notFound } from 'next/navigation'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import Link from 'next/link'

export const revalidate = 60

export default async function DistrictPage({ params }: { params: { id: string }}) {
  const sb = createPublicClient()
  const { data: rows, error } = await sb.from('district_scorecard')
    .select('*').eq('district_id', params.id)
  if (error) throw error

  // Header info: ak žiadne rows, fetch district + municipality cez district_map_features
  let header
  if (rows && rows.length) {
    header = {
      district_name: rows[0].district_name,
      municipality_id: rows[0].municipality_id,
      municipality_name: rows[0].municipality_name,
      vzn_id: rows[0].vzn_id,
      vzn_ref_url: rows[0].vzn_ref_url,
    }
  } else {
    const { data: mf } = await sb.from('district_map_features')
      .select('id, name, municipality_id, school_name').eq('id', params.id).maybeSingle()
    if (!mf) notFound()  // skutočne neexistujúci district = 404
    header = {
      district_name: mf.name,
      municipality_id: mf.municipality_id,
      municipality_name: null,
      vzn_id: null, vzn_ref_url: null,
    }
  }

  // Sort by condition_order via local labels map (SQL no longer returns it)
  const sorted = [...(rows ?? [])].sort((a, b) =>
    (CONDITION_LABELS_SK[a.condition_code]?.order ?? 99) - (CONDITION_LABELS_SK[b.condition_code]?.order ?? 99))

  return (
    <>
      <DisclaimerBanner alwaysShow />
      <h1>{header.district_name}</h1>
      {header.municipality_id && (
        <Link href={`/municipalities/${header.municipality_id}`}>{header.municipality_name ?? 'Obec'}</Link>
      )}
      {header.vzn_ref_url && <a href={header.vzn_ref_url} rel="noopener noreferrer nofollow" target="_blank">VZN</a>}
      <DistrictMiniMap districtId={params.id} />
      {sorted.length > 0
        ? <DistrictScorecard rows={sorted} />
        : <Alert>
            <AlertTitle>Bez verdikov</AlertTitle>
            <AlertDescription>Engine zatiaľ nehodnotil tento obvod.</AlertDescription>
          </Alert>}
    </>
  )
}
```

### 4.5 `app/findings/page.tsx`

URL search params: `severity` (multi), `status`, `condition`, `page`. Page size 50. Use Next `searchParams` prop. Server-side filter cez `.in()` / `.eq()`.

### 4.6 `components/disclaimer-banner.tsx`

Banner fetchuje `methodology_version` + `engine_version` zo Server Componentu nadradeného layoutu (props) — neuvádza statický `...`. Persistence: **`localStorage`** podľa PRD (nie sessionStorage). Kľúč: `dismiss_disclaimer_session`.

```tsx
// Server wrapper (RSC) — fetch verzie
import { createPublicClient } from '@/lib/supabase/server'
import { DisclaimerBannerClient } from './disclaimer-banner.client'

export async function DisclaimerBanner({ alwaysShow = false }: { alwaysShow?: boolean }) {
  const sb = createPublicClient()
  const { data } = await sb.from('engine_metadata').select('methodology_version, engine_version').maybeSingle()
  return (
    <DisclaimerBannerClient
      alwaysShow={alwaysShow}
      methodologyVersion={data?.methodology_version ?? 'n/a'}
      engineVersion={data?.engine_version ?? 'n/a'}
    />
  )
}
```

```tsx
// disclaimer-banner.client.tsx
"use client"
import { useState, useEffect } from 'react'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

type Props = { alwaysShow: boolean; methodologyVersion: string; engineVersion: string }

export function DisclaimerBannerClient({ alwaysShow, methodologyVersion, engineVersion }: Props) {
  const [hidden, setHidden] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  useEffect(() => {
    if (!alwaysShow && localStorage.getItem('dismiss_disclaimer_session') === '1') setDismissed(true)
  }, [alwaysShow])
  if (hidden || dismissed) return null
  return (
    <Alert>
      <AlertTitle>Demo, nie oficiálny výklad</AlertTitle>
      <AlertDescription>
        Toto demo zobrazuje analytické výstupy nad čiastočnými verejnými dátami pre 12 školských obvodov mesta Prešov. <strong>Nie je oficiálnym výkladom súladu s § 44 zákona č. 596/2003.</strong> Hodnoty <code>INCOMPLETE</code> / <code>INSUFFICIENT_DATA</code> znamenajú dátovú medzeru, nie nesúlad. Verzia metodiky: <code>{methodologyVersion}</code>. Verzia enginu: <code>{engineVersion}</code>.
      </AlertDescription>
      {!alwaysShow && (
        <Button onClick={() => { localStorage.setItem('dismiss_disclaimer_session','1'); setHidden(true) }}>Zatvoriť na túto návštevu</Button>
      )}
    </Alert>
  )
}
```

### 4.7 Error / not-found / loading

- `app/error.tsx` (root): client component, ukáže „Stala sa chyba. Skúste znova alebo nahláste správcovi" + reset button.
- `app/not-found.tsx`: „Obvod nenájdený."
- `app/loading.tsx`: skeleton stránky.

---

## 5. Testy (Haiku)

### 5.1 Test DB izolácia (povinné pred testami)

Testy bežia voči **dedikovanému staging Supabase projektu** (env `STAGING_DATABASE_URL` + `NEXT_PUBLIC_STAGING_SUPABASE_URL` + `STAGING_ANON_KEY`). Schéma je `skolske_obvody` (rovnaká ako prod — žiadny `_test` suffix, lebo app je hardcoded na `skolske_obvody`). Izolácia = oddelená DB, nie oddelená schéma.

Seed:
```bash
psql "$STAGING_DATABASE_URL" -f db/migrations/0001_init.sql
psql "$STAGING_DATABASE_URL" -f db/migrations/0010_sprint_c_read_views.sql
psql "$STAGING_DATABASE_URL" -f tests/fixtures/seed_sprint_c.sql
```

`tests/fixtures/seed_sprint_c.sql` obsahuje:
- 1 municipality (Prešov, slug='presov')
- 1 municipality (Košice — kontrolný non-Prešov záznam pre scope isolation test)
- 22 districtov (12 Prešov pre composition parity + 10 syntetic Prešov edge cases, + 1 Košice pre leak test)
- per district 9 verdictov so kontrolovaným value, evidence_text obsahuje `[email]`-able prípady + non-allowlist provenance URL
- per district relevantné findings

### 5.2 Unit / integration tests (Vitest, voči staging DB)

Žiadny test nepoužije anon REST na write. Všetok write ide cez `psql $STAGING_DATABASE_URL`. Anon REST sa používa iba na **read** v assert fázach.

1. `unit/composition-parity.test.ts` — pre každý z 22 fixture cases existuje seedovaný `district_id`. Test: REST `select composition_color from district_compositions where district_id = ?` → assert == `fixture.expected`. 22/22 musí prejsť.
2. `unit/scope-isolation.test.ts` — pre 6 dátových views (seed obsahuje 1 Košice municipality + 1 Košice district + 1 Košice verdict + 1 Košice finding ako kontrolný kanárik):
   - `district_map_features`, `district_scorecard`: priamy stĺpec `municipality_id` → assert všetky == `presov_id` (z fixtures)
   - `district_compositions`: `municipality_id` nie je vo view → assert join `SELECT district_id FROM district_compositions` → load `districts` raw tabuľku (cez psql nie REST!) → každý district_id musí byť z `WHERE municipality_id = presov_id`
   - `findings_public`: priamy stĺpec `municipality_id` (alebo derivovaný z join — viď PLAN §2.4) → assert všetky == presov_id
   - `municipalities_summary`: assert iba 1 riadok (Prešov), `name = 'Prešov'`
   - `engine_metadata`: assert `verdicts_count == seed_presov_verdicts_count` (zo seed konštanty) a NIE `seed_total_verdicts_count` — overí, že Košice verdikt sa nepripočítal
3. `unit/sanitization.test.ts` — read assertions na seedované evidence_text s `[email]`/`[tel]`/`[rč]` markermi.
4. `unit/allowlist.test.ts` — read assertions na seedované provenance URL z allowlistu vs mimo.
5. `unit/severity-sort.test.ts` — `severity_rank` poradie (čistá unit, žiadna DB potrebná).
6. `unit/url-params.test.ts` — findings filter URL parser (čistá unit).
7. `unit/provenance-link.test.ts` — komponent unit (vitest + @testing-library/react), NULL prop → fallback text, valid → `<a rel target>`.
8. `unit/disclaimer-dismiss.test.ts` — **localStorage** behavior (nie sessionStorage).

Test runner pred behom unit/integration: assert `$STAGING_DATABASE_URL` set; ak nie → `test.skip('SKIPPED:no-staging-db')` pre integration testy (1–4), čisté unit (5–8) bežia vždy.

### 5.3 E2E (Playwright)

Test runner pred E2E:
- Pokus o `psql $STAGING_DATABASE_URL -f tests/fixtures/seed_sprint_c.sql`
- Ak staging nie je → `test.skip('SKIPPED:no-staging-db')` + log

E2E scenáre:
1. `home.spec.ts` — `/` → vidí disclaimer banner, 3 KPI karty (nenulové), CTA klik → `/map`
2. `map.spec.ts` — `/map` → ≥1 farebný polygón render, klik na konkrétny obvod (z fixture) → URL match `/districts/<uuid>`
3. `district.spec.ts` — `/districts/<seed_uuid>` → scorecard 9 riadkov, disclaimer prítomný (vždy), prvý riadok = S1
4. `findings.spec.ts` — `/findings` → ≥1 riadok, filter severity=critical → URL update, list update

Screenshoty: `/map` + `/districts/<uuid>` 1280×720 do `tests/screenshots/`.

### 5.4 Test scripts v package.json

```json
{
  "test": "vitest run",
  "test:e2e": "playwright test",
  "test:all": "npm run test && npm run build && npm run test:e2e"
}
```

---

## 6. Deploy (Sonnet po test pass)

```bash
cd projects/skolske-obvody-44
# 1. potvrď env vars
vercel env ls | grep -E "NEXT_PUBLIC_SUPABASE_(URL|ANON_KEY)" || vercel env add ...

# 2. preview deploy
vercel deploy --no-clipboard > /tmp/sprint-c-deploy.txt
PREVIEW_URL=$(tail -1 /tmp/sprint-c-deploy.txt)
echo "$PREVIEW_URL" > /tmp/sprint-c-preview.url

# 3. smoke test
for path in / /map /findings; do
  curl -fsS "$PREVIEW_URL$path" > /dev/null || fail "smoke $path"
done

# 4. screenshot
npx playwright screenshot "$PREVIEW_URL/map" /tmp/sprint-c-map.png --viewport-size=1280,720
npx playwright screenshot "$PREVIEW_URL/districts/<first_district_id>" /tmp/sprint-c-district.png --viewport-size=1280,720
```

---

## 7. Commit / PR

Branche: `feat/sprint-c-frontend` (vytvorená v §0).

Commit batches:
1. `feat(db): sprint C read-only views with PII sanitization + provenance allowlist` (migrácia + funkcie)
2. `feat(frontend): sprint C UI skeleton — map + scorecard + findings + drill-down` (app/ + components/ + lib/)
3. `test(sprint-c): unit + e2e tests for scope isolation, sanitization, allowlist, parity` (tests/)
4. `chore(deploy): vercel preview config` (vercel.json updates if needed)

PR voči `main`, draft (Vlado schvaľuje merge). Body podľa template z `AGENTS.md`: Summary, Test plan, Linear link (TBD).

---

## 8. GPT verify (stage 7)

Vstup pre GPT-5.5: diff `git diff main...feat/sprint-c-frontend`, screenshoty, test report.

Akceptačná hranica: `APPROVE` alebo `APPROVE_WITH_CHANGES`. `BLOCK` triggeruje re-iteráciu (Sonnet fix) max 2×.

---

## 9. Vlado deliverables

Po hotom Sprint C (každý z týchto musí byť doručený do Telegramu):
1. Vercel preview URL.
2. Screenshot `/map` (1280×720, čitateľný).
3. Screenshot `/districts/<konkrétny obvod>` (1280×720).
4. Krátky text-update (čo demo ukazuje, čo NIE — disclaimer-style, ľudská reč).
5. Branch + commit hash + PR link.

---

## 10. Známe limity Sprint C

- Engine zatiaľ má verdikty len pre 12 Prešovských obvodov → ostatné mesto/región zostáva sivé („nezhodnotené").
- `Š1/Š2/Š3` často INCOMPLETE → demo ukazuje GAP-y, nie compliance verdikty.
- OSM tile policy: demo provoz < 10k req/deň; pri škálovaní → MapTiler/Stadia v ďalšom sprinte.
- Žiadne CSV / PDF export — out of scope.
- Žiadny user-facing zápis.

---

## 11. Open question pre Vlada (pred deploy)

1. Vercel projekt: nový (`skolske-obvody-44`) alebo existujúci? Ak nový — Sonnet ho vytvorí pri prvom `vercel deploy` (default).
2. Staging Supabase: existuje dedikovaný staging projekt s vlastnými `STAGING_DATABASE_URL` + `STAGING_ANON_KEY`?
   - Ak ÁNO: testy bežia priamo voči nemu, schema = `skolske_obvody` (rovnaká ako prod).
   - Ak NIE: integration testy (1–4) sa **skipnú** so značkou `SKIPPED:no-staging-db`, čisté unit testy (5–8) bežia vždy, E2E sa skipne. Sprint C pokračuje na deploy s redukovaným pokrytím a Vlado dostane warning.

Default ak Vlado nereaguje pri checkpointe pred E2E: pokračuj s **skip integration + E2E**, deploy preview a do Vlado-update zahrň warning „E2E neoverené pre absenciu staging DB".

## 12. Supabase REST exposure check (pred-flight pred testami)

Po aplikovaní migrácie `0010` Sonnet overí, že PostgREST REST API skutočne vystavuje schému `skolske_obvody`:

```bash
curl -fsS \
  -H "apikey: $NEXT_PUBLIC_SUPABASE_ANON_KEY" \
  -H "Accept-Profile: skolske_obvody" \
  "$NEXT_PUBLIC_SUPABASE_URL/rest/v1/engine_metadata?select=last_engine_run_at" \
  > /tmp/rest-probe.json || fail "schema not exposed in PostgREST"
```

Ak fail → BLOCKER do `BLOCKERS.md`: „Supabase: pridať `skolske_obvody` do Database Settings → API → Exposed schemas". F2 eskaluje Vladovi (Supabase setting nie kód).
