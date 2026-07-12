# Dátový zdroj: Atlas rómskych komunít 2019 (VLA-33)

## Čo je to a odkiaľ pochádza

**Atlas rómskych komunít 2019** — verejná databáza Úradu splnomocnenca vlády SR
pre rómske komunity (ÚSVRK). Tretie vydanie atlasu (po 2004 a 2013), zverejnené
na oficiálnej stránke `romovia.vlada.gov.sk`.

- **Dáta (XLSX):** https://www.romovia.vlada.gov.sk/site/assets/files/1111/ark2019_c_verejna.xlsx
- **Metodika (DOCX):** https://www.romovia.vlada.gov.sk/site/assets/files/1111/manual_k_verejnej_databaze_atlasu_romskych_komunit_2019_final.docx
- **Zoznam obcí 2019 (PDF, doplnkový):** https://www.romovia.vlada.gov.sk/site/assets/files/1111/atlas_-_obce_2019_13102020.pdf
- **Stiahnuté:** 2026-07-12

### Prečo verzia 2019, nie 2025

Zadanie (VLA-33) odkazovalo na skrátené URL
`.../assets/files/1111/ark2` a `.../assets/files/1111/manual_k_verejnej_databa`
(z hlasového prepisu). Obe boli len orezané verzie skutočných 2019 URL
(`ark2019_c_verejna.xlsx`, `manual_k_verejnej_databaze_atlasu_romskych_komunit_2019_final.docx`)
— overené priamo na `romovia.vlada.gov.sk`.

ÚSVRK v roku 2024–2026 pripravuje nástupcu (**SMARK 2025** — Sociografické
mapovanie rómskych komunít), ale k dátumu sťahovania (2026-07-12) je z neho
verejne dostupný iba zoznam ~1000+ obcí a dotazníky (`otazky_2025_obec.pdf`,
`otazky_2025_lokality.pdf`, `zoznam_obci_smark_2025_web.xlsx`) — **žiadna
výsledková databáza s podielom rómskych obyvateľov**. Stránka SMARK 2025 sama
uvádza, že podrobná databáza a nový mapový portál budú publikované až
neskôr. Atlas 2019 je preto najaktuálnejší reálny, publikovaný zdroj s
konkrétnymi (intervalovými) číslami k dátumu tejto úlohy.

## Štruktúra a čo presne ingestujeme

Zošit `ark2019_c_verejna.xlsx` má 3 hárky: `obce` (825 obcí), `osídlenia`
(1052 lokalít), `porovnanie`. Táto úloha používa **iba hárok `obce`** —
úroveň celej obce, nie lokality/osídlenia (tie ostávajú doménou
`so_mrk_localities`, DEMO/mock, viď nižšie).

Použitý stĺpec: **F — „Podiel rómskych obyvateľov (intervaly)"**. Manuál
(„Opis vybraných údajov") ho definuje ako *„Približne aké % obyvateľstva z
danej obce sú Rómovia."* Hodnota je vždy 10-bodový interval
(`1%-10%`, `11%-20%`, …, `91%-100%`) — **Atlas nikdy nepublikuje presné %**,
takže táto appka ho tiež nikdy nevymýšľa/nedopočítava.

Filter: `Okres = 'Prešov'` (stĺpec B) → 32 obcí. Všetkých 32 je ingestovaných
do `skolske_obvody.atlas_roma_share` (nie len tie nad prahom) — prah sa
aplikuje až vo view `so_atlas_roma_municipalities`, cez konfiguračnú tabuľku
`skolske_obvody.atlas_roma_share_config` (`highlight_threshold_pct`, default
20), takže zmena prahu nevyžaduje nové ingestovanie dát.

`roma_share_band_low` je dolná hranica intervalu (napr. `31%-40%` → `31`);
porovnanie `roma_share_band_low > threshold` je konzervatívne — obec sa
označí ako "nad prahom X %" len keď X leží striktne pod celým jej intervalom.

## Prepojenie na školský obvod

Tabuľky `skolske_obvody.districts` v tejto appke pokrývajú výhradne 12
školských obvodov mesta Prešov (`districts.municipality_id` je vždy Prešov)
plus, podľa VZN, pevný zoznam susedných obcí pooled do niektorého z týchto
obvodov (`so_shared_municipality_areas`, VLA-21/VLA-31). View
`so_atlas_roma_municipalities` preto priraďuje `assigned_district_id/name`
**len** cez tento shared-catchment zoznam — pre obec mimo neho je pole `NULL`
a UI to zobrazí čestne ako "nie je súčasťou žiadneho evidovaného obvodu v
tomto systéme", nikdy nevymyslený obvod. Z 22 obcí nad prahom (aktuálny
default 20 %) má známy obvod 5: Kendice, Mirkovce, Abranovce, Ruská Nová Ves,
Varhaňovce.

## Vzťah k existujúcej DEMO MRK vrstve — NEZAMIEŇAŤ

| | `so_mrk_localities` (existujúce, VLA-14/16/17) | `so_atlas_roma_municipalities` (VLA-33, táto úloha) |
|---|---|---|
| Stav | **DEMO/mock**, `is_demo=true` badge | **Reálne**, žiadny `is_demo` stĺpec |
| Úroveň | budova/lokalita (bod) | celá obec (polygón) |
| Rozsah | iba mesto Prešov | celý Okres Prešov |
| Zdroj | Atlas MRK (obec-level polygón z `skolske_obvody.mrk_atlas`, DEMO seedy z `0028_demo_mode_verdicts_seed.sql`) | Atlas rómskych komunít 2019, priamo z verejného XLSX |
| Vizuál na mape | fialový hatch pattern | plná tyrkysová výplň s prerušovaným okrajom |

## Kde v kóde

- Migrácia: `scripts/sql/0052_atlas_roma_share.sql`
- Typ: `SoAtlasRomaMunicipality` (`lib/supabase/types.ts`)
- Fetch: `fetchAtlasRomaMunicipalities()` (`app/map/page.tsx`)
- Render: `region-map.client.tsx`, pane `atlasRoma`, trieda `so-atlas-roma-area`
- E2E: `tests/e2e/vla33-atlas-roma.e2e.mjs`, proof: `docs/proof/vla33-atlas-roma.png`
