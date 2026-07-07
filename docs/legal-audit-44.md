# Právny audit § 44 — podmienky enginu vs. skutočné znenie zákona (VLA-19)

**Normatívny zdroj:** `docs/legal/zakon-321-2025-par-44.md` (doslovné znenie § 44
zákona č. 321/2025 Z. z., stiahnuté 2026-07-06 zo slov-lex.sk).
**Podnet:** klientsky defekt report (Vlado) 2026-07-06, defekty 5, 6, 8.
**Direktíva vlastníka:** demo nesmie vymýšľať nové druhy porušení ani právne
dôvody. Každý FAIL scenár sa mapuje 1:1 na skutočné ustanovenie § 44; mock dáta
vytvárajú scenár, ale citovaný právny základ musí byť doslovne správny.
Podmienka bez opory v zákone smie existovať len ako jasne označený neprávny
(metodický) indikátor a jej FAIL sa nikdy neprezentuje ako porušenie § 44.

## Skutočná štruktúra § 44 ods. 8 (doslovne)

> (8) Pri určovaní verejných školských obvodov sa vo vzájomnej súvislosti
> a s primeraným vyvážením zohľadňuje najmä
> a) kapacita budov zriaďovateľa alebo školy, v ktorých sa uskutočňuje výchova
>    a vzdelávanie alebo ktoré sú svojím funkčným usporiadaním na výchovu
>    a vzdelávanie vhodné,
> b) vzdialenosť z miesta pobytu dieťaťa alebo žiaka podľa odseku 1 do školy
>    tak, aby nebolo ohrozené plnenie povinného predprimárneho vzdelávania
>    alebo povinnej školskej dochádzky,
> c) dopravná infraštruktúra obce,
> d) právo detí a žiakov podľa odseku 1 na vzdelávanie v štátnom jazyku alebo
>    jazyku príslušnej národnostnej menšiny,
> e) dodržiavanie zákazu segregácie vo výchove a vzdelávaní a
> f) princíp inkluzívneho vzdelávania.

Dôležité: ods. 8 sú **hľadiská („zohľadňuje sa najmä… s primeraným vyvážením“)**,
nie číselné limity. Zákon nikde v § 44 neuvádza 2 km, 30 minút, počet prestupov
ani bariéry na trase. Zákon však tieto hľadiská sám nazýva „podmienky podľa
odseku 8“ (ods. 4, 10, 11).

## Auditná tabuľka

| Kód | Čo engine skutočne meria | Ustanovenie § 44 (doslovná opora) | Sémantika verdiktu | Kotva textu | Nález auditu |
|---|---|---|---|---|---|
| S1 | Demo: počet adries obvodu, ktoré (a) ležia v geometrii iného obvodu, než im určuje uličný zoznam VZN, (b) nepokrýva žiadny obvod. Real: proxy geometrické pokrytie obce. | ods. 1: „obec určuje všeobecne záväzným nariadením jeden verejný školský obvod samostatne pre… každú základnú školu“; „Verejné školské obvody pre príslušný druh školy sa nesmú prekrývať okrem verejného školského obvodu podľa odseku 6.“ | zákonná podmienka (FAIL → RED) | `engine/c_s1.py`, `lib/compliance/labels.ts` | **MISMATCH (defekt 8):** text „priradených do NESPRÁVNEHO obvodu“ a „0 nepokrytých“ — adresa pokrytá dvoma obvodmi je PREKRYV, adresa bez obvodu je MEDZERA V POKRYTÍ; „nesprávny obvod“ nie je z dát doložiteľný. Opravené: presné pomenovanie merania, bez frázy „nesprávny obvod“, nulové kategórie sa nevymenúvajú. |
| S2 | Tá istá plná adresa (ulica + číslo) priradená 2+ obvodom rovnakého typu a jazyka. | ods. 1 (zákaz prekrývania obvodov pre rovnaký druh školy) a ods. 7 (zákaz prekrývania obvodov škôl s rovnakým vyučovacím jazykom menšiny). | zákonná podmienka (FAIL → RED) | `engine/c_s2.py`, `engine/runner.py` | Citácia „§ 44 ods. 1 a 7“ **SPRÁVNA**. Label „Š2 — Topologické pokrytie“ v labels.ts/view je zastaraný (engine meria prekryv adries, nie topológiu polygónov) → premenované na „Š2 — Neprekrývanie obvodov“ + opis. |
| S3 | Počet verejných škôl zhodného typu v geometrii obvodu (očakáva sa práve 1). | ods. 1: „V každom verejnom školskom obvode sa určuje len jedna materská škola alebo jedna základná škola…“; ods. 2: „Jedna materská škola alebo jedna základná škola nemôže byť zaradená do viacerých verejných školských obvodov.“ | zákonná podmienka (FAIL → RED) | `engine/c_s3.py` | Citácia „§ 44 ods. 1“ **SPRÁVNA**. Bez zmeny sémantiky. |
| Pa | Vzdušná (priama) vzdialenosť geokódovaných adries obvodu k pridelenej škole; prah 2 000 m. | ods. 8 písm. b): „vzdialenosť z miesta pobytu dieťaťa alebo žiaka podľa odseku 1 do školy tak, aby nebolo ohrozené plnenie…“ — **bez číselného limitu**. | neprávny rizikový indikátor (FAIL/IND → ORANGE, nikdy RED) | `engine/c_pa.py`, `lib/compliance/labels.ts` | **MISMATCH (defekt 5):** citované písm. a) — to je o kapacite budov, nie o vzdialenosti. Prah 2 000 m (`PB_PASS_DISTANCE_M`) je náš metodický parameter dema, nie zákonný limit. Opravené: citácia → písm. b); text uvádza metriku (vzdušná čiara = aproximácia, reálna pešia trasa je spravidla dlhšia — P-b) a prah označuje ako metodický parameter dema. |
| Pb | Pešia trasa (OSRM) z reprezentatívnych bodov obvodu do školy; prahy 2 km / 30 min / 4 km. | ods. 8 písm. b) (vzdialenosť ako hľadisko, bez limitu). | neprávny rizikový indikátor (→ ORANGE) | `engine/c_pb.py` | Citácia písm. b) **SPRÁVNA**; prahy 30 min / 2 km / 4 km sú **vymyslené limity** → označené ako metodické parametre dema, nie zákon. |
| Pc | MHD trasa (demo: počet prestupov + minúty; real: ilustratívne Google Routes). | ods. 8 písm. c): „dopravná infraštruktúra obce“. | demo: neprávny indikátor (→ ORANGE); real: ilustratívne | `engine/c_pc.py` | Citácia písm. c) **SPRÁVNA**; pravidlo „viac ako jeden prestup = FAIL“ je **vymyslený limit** → označené ako metodický parameter dema. |
| Pd | Bariéry na trase (rušná cesta bez priechodu, železnica bez podchodu) — demo model; real INSUFFICIENT_DATA. | **ŽIADNA** — § 44 bariéry na trase nespomína. Písm. d) je o práve na vzdelávanie v štátnom jazyku alebo jazyku menšiny. | neprávny (metodický) indikátor (→ ORANGE); FAIL sa NIKDY neprezentuje ako porušenie § 44 | `engine/c_pd.py`, `lib/compliance/labels.ts` | **MISMATCH (defekt 6):** citácia „ods. 8 písm. d)“ je vymyslená právna argumentácia (písm. d) je jazykové právo). Opravené: citácia odstránená, P-d označený „bez priamej opory v § 44 — metodický indikátor bezpečnosti trasy“. |
| Pe | Koncentrácia budov MRK (Atlas 2019) v obvode → analytický signál. | ods. 8 písm. e): „dodržiavanie zákazu segregácie vo výchove a vzdelávaní“. | analytický signál (SIGNAL, mimo semaforu) | `engine/c_pe.py` | Citácia písm. e) **SPRÁVNA**. Bez zmeny sémantiky. |
| Pf | Zapísaní žiaci vs. kapacita pridelenej školy (EDUZBER/demo). | ods. 8 písm. a): „kapacita budov zriaďovateľa alebo školy…“. | analytický signál (SIGNAL, mimo semaforu) | `engine/c_pf.py` | **MISMATCH:** citované písm. f) — to je „princíp inkluzívneho vzdelávania“, nie kapacita. Opravené: citácia → písm. a). |
| JAZYK | Vyučovací jazyk pridelenej školy (menšinový → podnet). | ods. 8 písm. d): „právo detí a žiakov… na vzdelávanie v štátnom jazyku alebo jazyku príslušnej národnostnej menšiny“; kontext ods. 6 a 7 (ďalšie obvody pre menšinové školy). | podnet mimo semaforu (SIGNAL/NO_SIGNAL; nikdy nevstupuje do semaforu — invariant) | `engine/c_lang.py`, `lib/compliance/labels.ts`, `app/findings/scenarios.ts` | **MISMATCH:** texty tvrdili „jazyk NIE je podmienkou § 44 / podnet nad rámec § 44“ — v rozpore s ods. 8 písm. d). Opravené: jazyk je hľadiskom podľa písm. d); v tomto nástroji sa vyhodnocuje ako samostatný podnet mimo semaforu (invariant zachovaný). Label → „Jazykový podnet (mimo semaforu)“. |

## Ďalšie kotvy textov mimo tabuľky podmienok

| Miesto | Nález | Akcia |
|---|---|---|
| `engine/coverage_gaps.py` `REASON_VZN_GAP_SK` | Parafráza „§ 44 ods. 1: každá adresa musí patriť práve jednému obvodu“ — zákon to takto doslovne nehovorí (hovorí: obec určuje obvod pre každú školu; obvody sa nesmú prekrývať). | Preformulované na doložiteľné znenie, citácia § 44 ods. 1 zachovaná. |
| `app/page.tsx`, `components/disclaimer-banner.client.tsx`, `app/o-metodike/page.tsx` | Citovaný „§ 44 zákona č. 596/2003 Z. z.“ — § 44 (verejný školský obvod) je v zákone č. 321/2025 Z. z.; 596/2003 je predchádzajúci predpis (obvody tam upravoval § 8). | Číslo zákona opravené na 321/2025. |
| `app/o-metodike/page.tsx` (karty P-a, P-b, P-c) | Prahy 2 km / 30 min / 1 prestup podané ako norma („nemá mať školu vzdialenú viac než 2 km“). | Preformulované: metodické parametre dema, zákon limit neurčuje. |
| `app/o-metodike/page.tsx` (tabuľka „Ako vyhodnocujeme § 44“, sekcia Š4/Pa-kapacita) | Zastaraná taxonómia (Š4, Pa=kapacita, Š3=segregácia) nezodpovedá aktuálnemu enginu ani zákonu. | Mimo rozsah VLA-19 (nie evidence-text) → backlog v `docs/ISSUES.md`. |
| DB tabuľka `skolske_obvody.finding_explanations` (AI vysvetlenia) | Obsahuje vymyslené právne tvrdenia („Podľa § 44 nemá byť škola vzdialená viac než 2 km“, Pc/Pd FAIL ako „porušenie podľa § 44“). Tabuľka aktuálne NIE JE konzumovaná žiadnym UI komponentom (mŕtve dáta zo staršieho šprintu). | Mimo rozsah VLA-19 → backlog v `docs/ISSUES.md` (regenerovať z opravených textov alebo odstrániť pred oživením UI). |
| `scripts/sql/0032_demo_inputs_seed.sql`, `scripts/sql/0036_demo_mode_inputs.sql` | Interné demo poznámky citujú „ods. 8 f)“ pre kapacitu a „nesprávny obvod“ pre S1. Nie sú user-facing. | Texty v súboroch opravené (budúce seedy); DB poznámky sú interné provenance. |

## Povolené citácie

Jediné právne citácie, ktoré sa smú vyskytovať v user-facing textoch
(labels.ts, engine evidence/methodology texty, app texty). Strojovo kontrolované
testom `tests/test_legal_citations.py`.

| Citácia | Doslovná opora (skrátene) |
|---|---|
| `§ 44 ods. 1` | povinnosť obce určiť VZN obvod pre každú školu; jedna škola na obvod; zákaz prekrývania obvodov pre rovnaký druh školy |
| `§ 44 ods. 2` | obvod pre celú obec alebo časť; jedna škola nemôže byť vo viacerých obvodoch |
| `§ 44 ods. 6` | ďalší verejný školský obvod pre školy s vyučovacím jazykom menšiny |
| `§ 44 ods. 7` | zákaz prekrývania obvodov škôl s rovnakým vyučovacím jazykom menšiny |
| `§ 44 ods. 1 a 7` | kombinovaná citácia zákazov prekrývania (S2) |
| `§ 44 ods. 8` | hľadiská určovania obvodov (súhrnne) |
| `§ 44 ods. 8 písm. a)` | kapacita budov zriaďovateľa alebo školy |
| `§ 44 ods. 8 písm. b)` | vzdialenosť z miesta pobytu do školy (bez číselného limitu) |
| `§ 44 ods. 8 písm. c)` | dopravná infraštruktúra obce |
| `§ 44 ods. 8 písm. d)` | právo na vzdelávanie v štátnom jazyku alebo jazyku menšiny |
| `§ 44 ods. 8 písm. e)` | dodržiavanie zákazu segregácie |
| `§ 44 ods. 8 písm. f)` | princíp inkluzívneho vzdelávania |

Zakázané vzory (test ich aktívne odmieta v user-facing kóde):

- citácia `§ 44 ods. 8 písm. a)` v súvislosti so vzdialenosťou (Pa),
- citácia `§ 44 ods. 8 písm. d)` v súvislosti s bariérami (Pd),
- citácia `§ 44 ods. 8 písm. f)` v súvislosti s kapacitou (Pf),
- „zákona č. 596/2003“ ako zdroj § 44 v UI textoch,
- prahy (2 km, 30 min, prestupy) podané ako zákonný limit — vždy „metodický
  parameter dema“.

## Mapovanie law_ref checkerov (kontrolované testom)

| Checker | law_ref po oprave |
|---|---|
| `engine/c_s1.py` | `§ 44 ods. 1` |
| `engine/c_s2.py` | `§ 44 ods. 1 a 7` |
| `engine/c_s3.py` | `§ 44 ods. 1` |
| `engine/c_pa.py` | `§ 44 ods. 8 písm. b)` |
| `engine/c_pb.py` | `§ 44 ods. 8 písm. b)` |
| `engine/c_pc.py` | `§ 44 ods. 8 písm. c)` |
| `engine/c_pd.py` | *(žiadna citácia — „bez priamej opory v § 44“)* |
| `engine/c_pe.py` | `§ 44 ods. 8 písm. e)` |
| `engine/c_pf.py` | `§ 44 ods. 8 písm. a)` |
| `engine/c_lang.py` | `§ 44 ods. 8 písm. d)` |
