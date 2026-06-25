# Sprint M — PRD: MVP Map Redesign + Metodika Expansion

**Status:** Active
**Created:** 2026-06-25
**Driver:** Vlado klient demo (pondelok), portál ako MVP demo pre PSK

## Goal

Premeniť `/map` z technickej galérie vrstiev na **čistý, prehľadný nástroj na identifikáciu presahov a vizualizáciu školských obvodov**, a metodiku z formulky na **dôveryhodný popis postupu pre nezávislého analytika**.

## Why

Vlado konečnému klientovi (PSK + samosprávy) prezentuje portál ako **MVP produkt**, ktorý ukazuje, ako budú obvody vyzerať keď bude proces digitálny. Súčasný stav (Voronoi krížom-krážom čiary cez domy, 7+ technických vrstiev, šum) klienta zmätie a podkopáva dôveru. Analytici/oponenti potrebujú metodiku vidieť do detailu, aby produkt vedeli buď schváliť alebo vrátiť s konkrétnou pripomienkou.

## User-facing changes

### Mapa (`/map`)

**Default zobrazenie:**
- LEN: obvody (sýto farebné, hrubé hranice 3px, deterministická per-obvod farba) + školy (markers s názvami) + prekryvy zvýraznené šrafovaním
- VYPNUTÉ default: Voronoi (zachované v DB pre engine, ale OFF na mape), MRK lokality, Adresy z VZN (Google), Domy z VZN (Google)
- ODSTRÁNENÉ: Google Geocoded hull (Sprint G/I) — úplne von z UI aj kódu

**Hranice obvodov:**
- Nahradiť Voronoi krížom-krážom čisté polygóny po uliciach (snap na OSM street geometry kde to dáva zmysel)
- Hranica medzi dvomi obvodmi ide stredom ulice, ak je tam logické rozdelenie (párne vs nepárne čísla domov)
- Žiadne vlnovky cez stredy ulíc, žiadne polygóny rozdeľujúce dom napoly
- Tam, kde nemáme presné dáta, použiť **mockdata** označené ako demo (banner pod mapou)

**Per-house dot v obvod farbe:**
- Pri zoom-in (úroveň 16+) zobraziť bodky jednotlivých domov v presnej farbe ich obvodu — okamžitá vizuálna kontrola "kam tento dom patrí"

**Prekryv zvýraznenie:**
- Plochy, kde 2+ obvody hovoria "tento dom patrí mne" → šrafované žltým + tooltip "PREKRYV: tento dom patrí podľa VZN do 2 obvodov (Š3 violation)"

**Banner pre demo režim:**
- Pod mapou alebo nad ňou: "Demo dáta — Register adries MŠSR nedostupný. Ukazujeme cieľový stav portálu. Reálne dáta po sprístupnení registra."

### Metodika (`/o-metodike`)

Rozšíriť o 4 sekcie:

1. **"Ako získavame dáta o obvodoch"** — flow: mestské weby → scrape VZN PDF/HTML → parser ulíc (žargón VZN: "Bajkalská 1–47 párne") → Google Geocoding API (street + house) → uloženie do `street_geocodes` + `house_geocodes` → priradenie do obvodu (Voronoi / VZN priame)
2. **"Ako vyhodnocujeme § 44 zákona 321"** — kritériá Š1-Š4 + Pa-Pb s definíciami (čo je input, čo testujeme, čo je výsledok), príklady FAIL vs PASS
3. **"Príklady z reálnej praxe"** — 3 screenshoty: dobrý obvod (clean) / prekryv (žltá šrafa) / ostrov segregácia (červené) + 2-3 vety komentár ku každému
4. **"Čo robíme, čo nerobíme"** — transparency: ktoré údaje berieme, z akých zdrojov, čo NEvyhodnocujeme (napr. kapacita budov z EDUZBER = GAP), kde sú limity

## Acceptance Criteria

**Mapa:**
- [ ] Default page load `/map` ukazuje len obvody + školy + prekryvy. Žiadne Voronoi krížom-krážom čiary viditeľné default.
- [ ] Layer control má tieto toggle (v poradí): Obvody (ON), Školy (ON), Prekryvy (ON), Domy z VZN (OFF), MRK lokality (OFF). Voronoi NIE je v ovládači viditeľná pre používateľa.
- [ ] Žiadny odkaz na "Google Geocoded hull (Sprint G/I)" nikde v UI.
- [ ] Per-obvod farba je deterministická a stála medzi page loadmi.
- [ ] Hranice obvodov sú minimálne 3px hrubé, sýta farba.
- [ ] Pri zoom-in 16+ vidno per-house dot v farbe svojho obvodu.
- [ ] Banner "Demo dáta — Register adries MŠSR nedostupný" je viditeľný.
- [ ] Aspoň 2 prekryvy a 1 ostrov sú vizualizované (mockdata OK).

**Metodika:**
- [ ] `/o-metodike` má 4 nové sekcie podľa štruktúry vyššie.
- [ ] V sekcii "Príklady z reálnej praxe" sú 3 screenshoty s komentárom.
- [ ] V sekcii "Ako vyhodnocujeme § 44" sú definované všetky kritériá Š1-Š4 + Pa-Pb so vstupmi/výstupmi.
- [ ] Slovenčina, profesionálny ale prístupný tón.

**Tech:**
- [ ] `npm run build` PASS
- [ ] `npm run lint` PASS
- [ ] Vercel deploy úspešný, URL https://skolske-obvody-44.vercel.app/map funguje
- [ ] Mobile responzívne (375px width OK)

## Out of scope

- Real-time integrácia s Registrom adries MŠSR (čaká na Sprint M+ keď bude prístup)
- Engine algoritmus zmena — engine ostáva ako je (Voronoi výsledky), len vizualizácia sa mení
- Per-house geocoding pre nové ulice — pracujeme len so súčasným datasetom

## Constraints

- F2 dostupný cez Telegram počas práce CC
- Vlado žiada dokončené dnes do polnoci CEST (2026-06-25 23:59)
- Single-branch deploy, žiadne pivots
- Mockdata MUSIA byť jasne označené (banner) aby sa nepoužilo na rozhodnutia

## Risks & mitigations

| Risk | Mitigácia |
|---|---|
| Mockdata polygóny neidú po uliciach pekne | Použiť OSM street geometry ako základ pre snap, fallback Voronoi pre nepokryté plochy |
| Per-house dots príliš heavy pri zoom-out | Renderovať len pri zoom 16+ |
| Demo banner si analytik prečíta zle | Banner napísať jasne: "DEMO. Reálne dáta po sprístupnení MŠSR registra." |
| Metodika screenshoty sa stanú zastaranými pri ďalších zmenách | Generovať programovo z Playwright pri build |
