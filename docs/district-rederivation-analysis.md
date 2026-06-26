# District re-derivation analysis (clean authoritative address data)

_Generated: 2026-06-26T20:47:37.259289+00:00_

Diagnosis only. No district geometry, address table, or legal Š1–Š3 verdict was changed by this analysis. Source of truth for the street→district assignment is `skolske_obvody.vzn_street_ranges`; the authoritative address inventory is the City-of-Prešov **Register adries a stavieb** (`skolske_obvody.register_adries`), cleaned into `skolske_obvody.register_adries_clean` (Step 2).

## 1. Clean address set (Step 2)

| Metric | Value |
|---|---:|
| Input register rows | 16307 |
| Dropped — not habitable (`obyvatelna≠true`) | 6905 |
| Dropped — withdrawn (`vyradena≠false`) | 0 |
| Dropped — empty street after normalisation | 0 |
| Dropped — exact duplicates on (street_norm, súpisné, orientačné) | 0 |
| **Kept (clean canonical)** | **9402** |
| Distinct clean streets | 400 |

Stored as `skolske_obvody.register_adries_clean` (+ public read view `public.so_register_adries_clean`). Street normalisation is identical to the geometry build's `NORM` (lower + unaccent + strip leading `Ulica ` + drop `č.`/dots + expand `Arm. gen.` + collapse whitespace).

## 2. (a) VZN street → district assignment on clean data

- Clean addresses total: **9402**
- Assigned to ≥1 district via a VZN street: **9291** (98.8%)
- **Coverage gap** (clean address whose street matches NO VZN district): **111**

A clean street the VZN assigns to several districts (range split) is counted for each such district, so per-district counts can sum above the assigned total. The per-house split is what geocoding resolves; for the count signal each district legitimately lists the street.

### Per-district authoritative counts (from the register, not Google guesses)

| District | Habitable addresses | Distinct streets |
|---|---:|---:|
| Základná škola, Kúpeľná č. 2 | 2193 | 105 |
| Základná škola, Československej armády č. 22 | 1339 | 54 |
| Základná škola, Lesnícka č. 1 | 1227 | 39 |
| Základná škola, Sibírska č. 42 | 1176 | 53 |
| Základná škola, Bajkalská č. 29 | 1019 | 30 |
| Základná škola, Prostějovská č. 38 | 630 | 23 |
| Základná škola, Šmeralova č. 25 | 575 | 19 |
| Základná škola, Važecká č. 11 | 546 | 19 |
| Základná škola, Mirka Nešpora č. 2 | 405 | 13 |
| Základná škola s materskou školou, Námestie Kráľovnej pokoja 4 | 390 | 16 |
| Základná škola, Májové námestie č. 1 | 223 | 19 |
| Základná škola, Šrobárova č. 20 | 186 | 15 |

### Coverage gaps — clean streets matching NO VZN district

10 distinct clean streets (111 addresses) are present in the authoritative register but are not assigned to any district by the VZN. These are real § 44 coverage candidates: addresses an authoritative register lists for which the VZN names no school.

| Sample spelling | Normalised | Addresses |
|---|---|---:|
| Herlianska | herlianska | 33 |
| Jabloňová | jablonova | 24 |
| L. Novomeského | l novomeskeho | 18 |
| Tóbikova ulica | tobikova | 11 |
| Jordánova ulica | jordanova | 10 |
| Rubínová ulica | rubinova | 5 |
| Kláštorná ulica | klastorna | 4 |
| Bukovčanova ulica | bukovcanova | 3 |
| Ulica Márie Kočanovej | marie kocanovej | 2 |
| K zvonici | k zvonici | 1 |

### VZN streets with zero clean register addresses

18 VZN street→district assignments have no habitable clean address in the register. Either the street has no habitable buildings, or the VZN spelling does not fold to a register spelling (see the separate `vzn-register-validation-report.md` for the spelling cross-check).

| District | VZN street (normalised) |
|---|---|
| Základná škola, Bajkalská č. 29 | lieskova |
| Základná škola, Československej armády č. 22 | jabonova |
| Základná škola, Kúpeľná č. 2 | prazska |
| Základná škola, Kúpeľná č. 2 | priemyselna |
| Základná škola, Lesnícka č. 1 | dlha |
| Základná škola, Lesnícka č. 1 | ku skare |
| Základná škola, Májové námestie č. 1 | l novomestskeho |
| Základná škola, Mirka Nešpora č. 2 | gorazdova |
| Základná škola, Mirka Nešpora č. 2 | jana lazorika |
| Základná škola, Mirka Nešpora č. 2 | kocelova |
| Základná škola, Mirka Nešpora č. 2 | pribinova |
| Základná škola, Mirka Nešpora č. 2 | rastislavova |
| Základná škola, Sibírska č. 42 | herlanska |
| Základná škola, Sibírska č. 42 | tulipanova |
| Základná škola, Šmeralova č. 25 | gerlachovska |
| Základná škola, Šmeralova č. 25 | racia |
| Základná škola, Šmeralova č. 25 | riecna |
| Základná škola, Šmeralova č. 25 | rybnicky |

## 3. (b) Geometric validation (748 geocoded points vs district polygons)

For each geocoded address we compute which district **polygon** (`districts.geom`) actually `ST_Covers` its real coordinate, and compare to the district its **VZN street** assigns. A point is a MATCH if the covering polygon is any of the street's VZN district(s).

| Outcome | Count |
|---|---:|
| Geocoded points checked | 748 |
| MATCH (coordinate in a VZN-assigned district polygon) | 666 |
| **MISMATCH (street says A, coordinate falls in polygon B)** | **72** |
| Coordinate falls in NO district polygon | 0 |
| Street not in any VZN district (no baseline to compare) | 10 |

Of 738 points that have both a VZN-street district and a covering polygon, **72 (9.8%) disagree** — the coordinate lands in a different district's polygon than its VZN street names. These are the § 44-relevant geometry/assignment inconsistencies.

Caveat on interpretation: the geocodes are a mix of `border_house` (real per-house coordinates) and `street_anchor` (one representative point per street). For a street the VZN **splits** across districts by house-number range (e.g. Sabinovská → Bajkalská/Šmeralova), a real house coordinate can legitimately fall in a third district's polygon, which surfaces here as a mismatch. Each mismatch is therefore a place to **look**, not an automatic error: it flags where the drawn polygon and the VZN street assignment do not agree on the ground.

### Mismatches per containing polygon district

| Polygon the coordinate fell into | Mismatched points |
|---|---:|
| Základná škola, Prostějovská č. 38 | 46 |
| Základná škola, Bajkalská č. 29 | 8 |
| Základná škola, Šrobárova č. 20 | 3 |
| Základná škola, Mirka Nešpora č. 2 | 3 |
| Základná škola, Kúpeľná č. 2 | 3 |
| Základná škola, Sibírska č. 42 | 3 |
| Základná škola, Važecká č. 11 | 3 |
| Základná škola, Májové námestie č. 1 | 1 |
| Základná škola, Československej armády č. 22 | 1 |
| Základná škola, Lesnícka č. 1 | 1 |

### Mismatch detail (address-level)

| Address | Street | VZN district(s) | Coordinate falls in polygon |
|---|---|---|---|
| Duklianska 6022/1 | Duklianska | Základná škola, Šmeralova č. 25 | Základná škola, Bajkalská č. 29 |
| Kotrádova 5161/1 | Kotrádova | Základná škola s materskou školou, Námestie Kráľovnej pokoja 4 | Základná škola, Bajkalská č. 29 |
| Kvašná voda súp. č. 12522 | Kvašná voda | Základná škola, Československej armády č. 22 | Základná škola, Bajkalská č. 29 |
| Ortáš 2638/1 | Ortáš | Základná škola, Československej armády č. 22 | Základná škola, Bajkalská č. 29 |
| Plavárenská 3366/1 | Plavárenská | Základná škola, Prostějovská č. 38 | Základná škola, Bajkalská č. 29 |
| Ružová 5205/1 | Ružová | Základná škola, Šmeralova č. 25 | Základná škola, Bajkalská č. 29 |
| Sadovnícka súp. č. 10498 | Sadovnícka | Základná škola, Československej armády č. 22 | Základná škola, Bajkalská č. 29 |
| Zlatnícka 15820/3 | Zlatnícka | Základná škola, Sibírska č. 42 | Základná škola, Bajkalská č. 29 |
| Medvedia 9026/1 | Medvedia | Základná škola, Šmeralova č. 25 | Základná škola, Československej armády č. 22 |
| Medzinárodného dňa žien 7581/1 | Medzinárodného dňa žien | Základná škola, Československej armády č. 22 | Základná škola, Kúpeľná č. 2 |
| Rezbárska 15508/2 | Rezbárska | Základná škola, Sibírska č. 42 | Základná škola, Kúpeľná č. 2 |
| Skromná súp. č. 1992 | Skromná | Základná škola, Československej armády č. 22 | Základná škola, Kúpeľná č. 2 |
| Pri majáku 14752/2 | Pri majáku | Základná škola, Májové námestie č. 1 | Základná škola, Lesnícka č. 1 |
| Višňová 6505/1 | Višňová | Základná škola, Šrobárova č. 20 | Základná škola, Májové námestie č. 1 |
| Námestie biskupa Vasiľa Hopka 12061/1 | Námestie biskupa Vasiľa Hopka | Základná škola, Šmeralova č. 25 | Základná škola, Mirka Nešpora č. 2 |
| Slivková 15278/1 | Slivková | Základná škola s materskou školou, Námestie Kráľovnej pokoja 4 | Základná škola, Mirka Nešpora č. 2 |
| Tomášikova 4855/12 | Tomášikova | Základná škola, Bajkalská č. 29; Základná škola, Prostějovská č. 38; Základná škola, Šmeralova č. 25 | Základná škola, Mirka Nešpora č. 2 |
| Astrová 14777/2 | Astrová | Základná škola, Sibírska č. 42 | Základná škola, Prostějovská č. 38 |
| Björnsonova 5031/1 | Björnsonova | Základná škola s materskou školou, Námestie Kráľovnej pokoja 4 | Základná škola, Prostějovská č. 38 |
| Sabinovská 12509/35 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 12509/37 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 13102/49 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 13348/43 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 13348/45 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 13945/125A | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 14139/121A | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 15741/139A | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5048/1 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5050/11 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5050/13 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5050/15 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5050/17 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5050/19 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5050/5 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5050/7 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5050/9 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5052/23 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5052/25 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5052/27 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5052/29 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5052/31 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5052/33 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5063/63 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5064/65 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5065/67 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5068/75 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5069/77 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5070/79 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5077/97 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5081/105 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5082/107 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5083/109 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5084/111 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5085/113 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5086/115 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5087/117 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5088/119 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5089/121 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5091/125 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5093/129 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5098/139 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5100/143 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Sabinovská 5101/145 | Sabinovská | Základná škola, Bajkalská č. 29; Základná škola, Šmeralova č. 25 | Základná škola, Prostějovská č. 38 |
| Na Rovni 14243/3 | Na Rovni | Základná škola, Kúpeľná č. 2 | Základná škola, Sibírska č. 42 |
| Školská 6686/1 | Školská | Základná škola, Kúpeľná č. 2 | Základná škola, Sibírska č. 42 |
| Tichá 12380/1 | Tichá | Základná škola, Šrobárova č. 20 | Základná škola, Sibírska č. 42 |
| Čergovská 7004/2 | Čergovská | Základná škola, Sibírska č. 42 | Základná škola, Šrobárova č. 20 |
| Magurská 7005/1 | Magurská | Základná škola, Sibírska č. 42 | Základná škola, Šrobárova č. 20 |
| Vlčia 14229/1 | Vlčia | Základná škola, Československej armády č. 22 | Základná škola, Šrobárova č. 20 |
| Na brehu 1060/1 | Na brehu | Základná škola, Lesnícka č. 1 | Základná škola, Važecká č. 11 |
| Pod Hrádkom 1116/1 | Pod Hrádkom | Základná škola, Lesnícka č. 1 | Základná škola, Važecká č. 11 |
| Suchoňova 13709/1 | Suchoňova | Základná škola, Lesnícka č. 1 | Základná škola, Važecká č. 11 |

## 4. (c) What this means for Š1 — honest scope

The § 44 methodology's **Š1** is *"the addresses of all PUPILS fall in the correct district"*. This register holds **BUILDINGS / addresses**, not pupil→school enrolment records. Therefore this analysis **does NOT by itself resolve Š1's pupil requirement** — we have no pupil data here.

What the clean data DOES provide:

- an **authoritative address inventory** per district (Section 2), replacing earlier Google-derived guesses with register counts;
- a **geometric consistency check** of the district derivation (Section 3): where the VZN-street assignment and the drawn polygon disagree for a real coordinate.

These are necessary inputs toward Š1, not a discharge of it. The legal Š1/Š2/Š3 verdicts are **left untouched**; the findings above are reported so a human can decide whether they change a verdict.

## 5. Artifacts

- `skolske_obvody.register_adries_clean` / `public.so_register_adries_clean` — clean canonical address set (additive).
- `scripts/sql/0026_register_adries_clean.sql` — schema.
- `ingest/build_register_adries_clean.py` — Step 2 builder.
- `ingest/rederive_districts_analysis.py` — Step 3 analysis (this report).

