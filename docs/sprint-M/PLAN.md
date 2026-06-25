# Sprint M — PLAN

5 sprintov, sériovo. Každý = jeden T-MAX job s fresh context. Po každom: commit + log update + ďalší sprint.

Branch: `feat/sprint-m-map-redesign` (vetva z `feat/sprint-c-frontend` @ `bd0d94b`)

## Sprint M-1: Map cleanup (~30 min)

**Cieľ:** Odstrániť technické vrstvy, ostaviť LEN obvody + školy + prekryvy default.

**Súbory:**
- `components/region-map.client.tsx` — layer control rewrite
- `app/map/page.tsx` — info text update (Voronoi info preč, "demo mode" pripravený)

**Konkrétne zmeny:**
1. Odstrániť `googleHullGroup` — variable + addTo logiku + control entry + props `geocodedGeom`
2. Default vrstvy ON: `districtsGroup`, `schoolsGroup`, `overlapsGroup` (ak má content)
3. Default vrstvy OFF: `voronoiGroup`, `mrkGroup`, `streetPointsGroup`, `housePointsGroup`
4. Layer control items:
   - "Obvody (12)" (ON)
   - "Školy (26)" (ON)
   - "Prekryvy obvodov" (ON ak má content)
   - "MRK lokality" (OFF, tooltip "Marginalizované Rómske Komunity — zdroj Atlas MRK")
   - "Domy z VZN (Google)" (OFF, tooltip "Jednotlivé domy z VZN, geokódované cez Google Maps API")
   - **Skryť úplne z control:** Voronoi (pre používateľa nepotrebné, len engine input)
5. Border weight 1.5 → 3, per-obvod farba (deterministicky z `getDistrictHue(id)`)
6. `app/map/page.tsx`: info text pod mapou aktualizovať (Voronoi preč)

**Success:** Build PASS, deploy preview, screenshot ukazuje čistú mapu s 3 vrstvami default.

## Sprint M-2: Clean street-snapped boundaries (~1.5 hod)

**Cieľ:** Nahradiť Voronoi krížom-krážom čisté polygóny obvodov ktoré idú po uliciach.

**Súbory:**
- `db/migrations/0020_clean_district_geom.sql` — nový view `so_district_clean_geom`
- `scripts/build_clean_district_geom.py` — generátor
- `components/region-map.client.tsx` — use clean geom namiesto voronoi
- `app/api/...` — endpoint ak treba

**Stratégia (cez Python skript):**
1. Pre každý obvod: zoberi všetky `house_geocodes` priradené k obvodu
2. Pre každý dom: nájdi najbližšiu OSM ulicu (cez Overpass API alebo lokálny extract)
3. Group domy po uliciach
4. Pre každú ulicu rozhodni: celá ulica patrí do obvodu? Alebo split párne/nepárne?
5. Generuj polygón obvodu ako OSM-street-aware union: buffer okolo ulíc obvodu (~30m) + clip k susedným obvodom (Voronoi medzi obvodmi sa zachová ale snap na street centerlines)
6. Pre nepokryté plochy (žiadne domy) fallback Voronoi
7. Uložiť ako GeoJSON do nového stĺpca `districts.geom_clean`

**Mockdata fallback:** Ak street-snap nepripravený do času, manuálne vytvoriť 3-4 ukážkové obvody clean polygónmi (geojson.io) a zvyšok Voronoi.

**Per-house dots:** Pridať Leaflet layer ktorý sa zobrazí len pri zoom 16+ (event listener), bodky v farbe obvodu pre každý house_geocode.

**Banner pre demo režim:** Pridať info banner pod mapu: "Demo dáta — Register adries MŠSR nedostupný..."

**Success:** Pri zoom-in vidím čisté hranice po uliciach, per-house dots v obvod farbe.

## Sprint M-3: Error scenarios demo (~1 hod)

**Cieľ:** 2-3 vizuálne demonštrácie chýb ktoré engine vie detegovať.

**Súbory:**
- `db/seed/demo_overlap.sql` — seed-ne 2 prekryvy
- `db/seed/demo_island.sql` — seed-ne 1 ostrov segregácia
- `components/region-map.client.tsx` — overlap rendering už existuje, len overiť že funguje s mockdata

**Konkrétne:**
1. Seed mockdata `district_overlaps`: 2 polygóny prekryvov medzi 2 ZŠ s žiakmi (žltý hatched)
2. Seed mockdata `district_islands`: 1 ostrov ďaleko od matky-obvodu, červeno ohraničený, tooltip "Ostrov segregácia (Š3 violation)"
3. Vrstva "Prekryvy" default ON
4. Findings panel zobrazuje tieto chyby s prioritou critical

**Success:** Na default mape vidím aspoň 2 prekryvy a 1 ostrov, klikatelné, s vysvetlením.

## Sprint M-4: Metodika expansion (~1.5 hod)

**Cieľ:** Rozšíriť `/o-metodike` o 4 sekcie pre analytickú dôveryhodnosť.

**Súbory:**
- `app/o-metodike/page.tsx` — pridať sekcie
- `public/methodology/` — screenshoty (alebo generuj cez Playwright)

**Konkrétne sekcie:**
1. **"Ako získavame dáta o obvodoch"** (~400 slov, flow diagram)
2. **"Ako vyhodnocujeme § 44 zákona 321"** (~600 slov, tabuľka kritérií)
3. **"Príklady z reálnej praxe"** (3 screenshoty + komentár)
4. **"Čo robíme, čo nerobíme"** (~300 slov, transparency)

**Screenshoty:** Použiť `npx playwright screenshot` na URLs: `/map?demo=clean`, `/map?demo=overlap`, `/map?demo=island`. Uložiť do `public/methodology/`.

**Success:** Stránka `/o-metodike` má 4 nové sekcie, navigácia funguje, screenshoty viditeľné.

## Sprint M-5: Deploy + verify + report (~30 min)

**Cieľ:** Merge do main, Vercel deploy, screenshoty, Telegram report Vladovi.

**Kroky:**
1. PR `feat/sprint-m-map-redesign` → `main` so screenshotmi v body
2. Self-review diff + visual proof
3. Merge
4. Vercel auto-deploy
5. Smoke test live URL: `/`, `/map`, `/o-metodike`, `/districts/<sample>`
6. Telegram report Vladovi: URL + 3 screenshoty + zhrnutie zmien

**Success:** Live URL beží, screenshoty Vladovi.

## Watchdog & self-check

- Status súbor: `.inflight/sprint-M-<N>.status` (každý sprint vlastný)
- Self-check cron: každých 3 min, payload "SELF-CHECK sprint-M-<N>: skontroluj T-MAX status, ak done a NOT processed → process + launch next sprint OR report failure"
- Po Sprint M-5: cron remove
