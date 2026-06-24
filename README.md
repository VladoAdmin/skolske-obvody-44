# Kontrola § 44 — Analytický portál školských obvodov

Analytický portál pre referentov RÚŠS a ministerstva školstva na overenie súladu
verejných školských obvodov s § 44 zákona č. 321/2025 Z. z. o školskej správe.

**Pilot:** Prešovský samosprávny kraj (PSK)  
**Stack:** Next.js 14 App Router · TypeScript strict · Tailwind CSS · shadcn/ui ·
MapLibre GL (OSM) · Supabase (Postgres + PostGIS) · OSRM/Valhalla

---

## Projekt v skratke

Portál operacionalizuje § 44 ods. 1, 7, 8 a pre každý školský obvod produkuje
obhájiteľný analytický výstup vo forme päticového verdiktu:

```
{ hodnota, dôvera (0–1), úplnosť dát (0–1), proveniencia, metóda }
```

Tri úrovne výstupu (nekombinovať):
1. **Tvrdé zákonné pravidlá** Š1–Š3 — PASS / FAIL / NEÚPLNÉ
2. **Kapacitno-dopravné indikátory** P-a–P-d — SPĹŇA / RIZIKO / MÁLO DÁT
3. **Sociálno-inkluzívne signály** P-e, P-f — SIGNÁL / BEZ SIGNÁLU / NEVYHODNOTENÉ

---

## Predpoklady

- Node.js 20+
- npm 10+
- Supabase projekt s PostGIS (pozri `db/README.md`)
- OSRM alebo Valhalla pre routing (pozri `services/routing/README.md`)

## Spustenie (development)

```bash
# 1. Nainštaluj závislosti
npm install

# 2. Nakonfiguruj premenné prostredia
cp env.example.txt .env.local
# Vyplň NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, ...

# 3. Spusti dev server
npm run dev
# → http://localhost:3000

# 4. Health check
curl http://localhost:3000/api/health
```

## DB schéma

```bash
# Aplikuj v Supabase SQL editore (v poradí):
db/schema/00001_extensions.sql   # PostGIS, uuid-ossp
db/schema/00002_core_tables.sql  # Hlavné tabuľky
db/schema/00003_vzn_tables.sql   # VZN tabuľka
db/schema/00004_rls.sql          # RLS skeleton
```

Detaily: `db/README.md`

## Build + lint

```bash
npm run build    # musí prejsť bez chýb
npm run lint     # musí prejsť bez chýb
```

## Routing (OSRM/Valhalla)

Detaily inštalácie: `services/routing/README.md`

## Štruktúra projektu

```
app/                    Next.js App Router stránky
  api/health/           GET /api/health — liveness probe
  map/                  Mapa PSK (MapLibre)
  findings/             Register nálezov (Sprint 4)
  municipalities/       Zriaďovatelia / scorecard (Sprint 4)
  reports/              Reporty + export (Sprint 4)
  admin/                Správa dát (Sprint 5)
components/
  layout/               AppHeader, AppNav
  map/                  MapClient (MapLibre), MapPlaceholder
libs/
  validators/           Zdieľaná validačná knižnica (ingestion + admin import)
services/
  routing/              OSRM/Valhalla klient stub
db/
  schema/               SQL schéma (aplikovať manuálne v Supabase)
middleware.ts           Rate-limit stub (Sprint 6)
vercel.json             Vercel deploy konfig
```

## Sprinty

| Sprint | Obsah |
|--------|-------|
| 0 (aktuálny) | Infraštruktúra — scaffold, DB schéma, routing stub, validator scaffold |
| 1 | Dátová vrstva + ingestion (WFS, VZN parser, adresné body) |
| 2 | Rule engine § 44 (Š1–Š3, P-a–P-d, verdikty) |
| 3 | Analytické výstupy (scorecard, register nálezov, izochróny) |
| 4 | Frontend portál (mapa + semafor, detailné obrazovky, WCAG) |
| 5 | Auth, role, admin konzola, monitoring |
| 6 | Bezpečnostný + a11y hardening |
| 7 | E2E testy (Playwright), finálny QA |

## Blokery (Sprint 0)

- **Supabase:** projekt musí vytvoriť Vlado/F2 → poskytnúť `NEXT_PUBLIC_SUPABASE_URL` + kľúče.
- **Google API kľúč:** vyžaduje Vlado → `GOOGLE_MAPS_API_KEY` (Routes API). Blokuje len P-c.
- **Vercel:** `vercel.json` je pripravený; prepojenie s repom cez Vercel dashboard (vyžaduje account linking — pozri nižšie).

## Licencia

Interný pilotný projekt. Nie je verejne licencovaný.
