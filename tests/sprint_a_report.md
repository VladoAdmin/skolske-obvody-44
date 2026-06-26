# Sprint A Report — § 44 Compliance Engine: Prešov Sample Run

**Engine version:** `565d0b2+demo`  
**Date:** 2026-06-24  
**Municipality:** Prešov (id `e74cc008-e6e3-4b4d-abae-0c62d240ba01`)  
**Districts:** 12  
**Conditions per district:** 9 (S1, S2, S3, Pa, Pb, Pc, Pd, Pe, Pf)

---

## 1. Row counts written to DB

| Table       | Rows written | Engine version  |
|-------------|-------------|-----------------|
| `verdicts`  | 108         | `565d0b2+demo`  |
| `findings`  | 99          | `565d0b2+demo`  |

Idempotent: re-running the same engine version performs UPSERT (overwrites).  
9 findings skipped = PASS verdicts (no finding written for PASS values).

---

## 2. Per-district semafor + breakdown

| District (short name)               | Color | S1         | S2   | S3   | Pa               | Pb    | Pb dist | Pc                | Pd               | Pe↑   | Pf↑          |
|-------------------------------------|-------|------------|------|------|------------------|-------|---------|-------------------|------------------|-------|--------------|
| ZŠ s MŠ Námestie Kráľovnej pokoja 4 | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | PASS | 720m    | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Bajkalská č. 29                  | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | RISK | 2 309m  | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Československej armády č. 22     | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | PASS | 1 312m  | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Kúpeľná č. 2                     | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | RISK | 2 980m  | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Lesnícka č. 1                    | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | PASS | 1 303m  | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Májové námestie č. 1             | RED   | INCOMPLETE | FAIL | PASS | INSUFFICIENT_DATA | RISK | 2 435m  | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Mirka Nešpora č. 2               | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | PASS | 1 769m  | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Prostějovská č. 38               | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | FAIL | 5 532m  | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Sibírska č. 42                   | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | PASS | 666m    | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Šmeralova č. 25                  | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | RISK | 2 718m  | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Šrobárova č. 20                  | RED   | INCOMPLETE | FAIL | PASS | INSUFFICIENT_DATA | PASS | 721m    | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |
| ZŠ Važecká č. 11                    | RED   | INCOMPLETE | FAIL | FAIL | INSUFFICIENT_DATA | PASS | 1 334m  | ILUSTR_NO_DATA    | INSUFFICIENT_DATA | SIGNAL | NOT_EVALUATED |

↑ = analytical signal panel only (Pe, Pf never enter legal semafor)

**Composition rule applied:** All 12 districts = RED because S2=FAIL for all.

---

## 3. Condition breakdown (all 12 districts)

| Code | Condition                    | PASS | FAIL | INCOMPLETE | RISK | INSUFF_DATA | SIGNAL | ILUSTR_NO_DATA | NOT_EVAL |
|------|------------------------------|------|------|------------|------|-------------|--------|----------------|----------|
| S1   | Pokrytie (coverage)          | 0    | 0    | 12         | —    | —           | —      | —              | —        |
| S2   | Neprekrývanie (non-overlap)  | 0    | 12   | 0          | —    | —           | —      | —              | —        |
| S3   | Jedna škola na obvod         | 2    | 10   | 0          | —    | —           | —      | —              | —        |
| Pa   | Kapacita budov               | —    | —    | —          | —    | 12          | —      | —              | —        |
| Pb   | Vzdialenosť/dochádzka        | 7    | 1    | 0          | 4    | —           | —      | —              | —        |
| Pc   | Dopravná dostupnosť          | —    | —    | —          | —    | —           | —      | 12             | —        |
| Pd   | Jazykové právo               | —    | —    | —          | —    | 12          | —      | —              | —        |
| Pe   | Zákaz segregácie (signal)    | —    | —    | —          | —    | —           | 12     | —              | —        |
| Pf   | Inklúzia ŠVVP (signal)       | —    | —    | —          | —    | —           | —      | —              | 12       |

---

## 4. Tests pass count

```
tests/test_engine_compose.py: 15 passed in 0.04s
```

All 15 tests passing, including 7 fixture tests and 8 gatekeeping invariant tests.

---

## 5. Conditions returning INSUFFICIENT_DATA / NOT_EVALUATED (expected for this sprint)

| Code | Value              | Reason | Data gap                          |
|------|--------------------|--------|-----------------------------------|
| S1   | INCOMPLETE (12×)   | No Register adries address_points in DB (0 rows). Proxy geometric check used. Confidence=0.4. | MV SR Register adries — open data access not yet confirmed |
| S2   | FAIL (12×)         | Real result: building-centroid concave-hull district geometries from Sprint B overlap massively (11–16 km²). This is a geometry quality issue (q6), not a VZN violation. Real VZN boundary-line polygons would likely resolve most overlaps. | Precise VZN polygon derivation (q6→q8) needed |
| S3   | FAIL (10×), PASS (2×) | Real result: with overlapping district hulls, multiple schools fall inside each district. 2 districts (Májové námestie, Šrobárova) happen to contain exactly 1 school spatially. | Same geometry quality root cause as S2 |
| Pa   | INSUFFICIENT_DATA (12×) | No EDUZBER capacity data in DB. student_count available but capacity absent → occupancy incalculable. | EDUZBER GAP — admin import needed |
| Pc   | ILUSTR_NO_DATA (12×) | GOOGLE_API_KEY not set in environment. Illustrative only. | Google API key from Vlado (pending) |
| Pd   | INSUFFICIENT_DATA (12×) | Minority-language enrollment dataset absent. school.teaching_language=SK for all Prešov schools; municipality.minority_language=NULL for Prešov. | Dataset jazykového nároku — Fáza 2 |
| Pe   | SIGNAL (12×)       | MRK Atlas polygons intersect with all Prešov districts (atlas data covers PSK broadly, not just MRK municipalities). All districts show > 10% MRK area share because MRK atlas covers wide areas. | Atlas MRK 2019 geometry is broader than expected for urban Prešov — may need municipality-level filter |
| Pf   | NOT_EVALUATED (12×) | ŠVVP dataset GAP — Fáza 2. | CVTI/RÚŠS ŠVVP data |

---

## 6. Root cause analysis: why all 12 = RED

The legal semafor is driven by **S2=FAIL for all 12 districts**. Root cause:

- District geometries are **concave-hull polygons derived from OSM building centroids** (Sprint B). These are approximation polygons that substantially overlap each other (11–16 km² overlaps detected).
- The legal Š2 condition requires **zero overlap** between same-type districts. The geometry artifacts violate this structurally.
- This is **correct behavior** — the engine correctly identifies that current district geometries do not meet Š2. The fix is higher-quality boundary-line polygons (q6→q8), not an engine change.

**Gatekeeping verified:**
- Pa=INSUFFICIENT_DATA does NOT cause RED (as per gatekeeping rule)
- Pc=ILUSTR_NO_DATA (is_illustrative=True) does NOT affect semafor
- Pe=SIGNAL stays in analytical-signals panel, does not affect legal color
- Pf=NOT_EVALUATED (is_mock=True) stays in analytical-signals panel

---

## 7. P-b walking distance highlights (OSRM real data)

| District                       | Verdict | Median dist | Median time |
|-------------------------------|---------|-------------|-------------|
| ZŠ Sibírska č. 42             | PASS    | 666 m       | ~8 min      |
| ZŠ Šrobárova č. 20            | PASS    | 721 m       | ~9 min      |
| ZŠ Námestie Kráľovnej pokoja  | PASS    | 720 m       | ~9 min      |
| ZŠ Lesnícka č. 1              | PASS    | 1 303 m     | ~16 min     |
| ZŠ Československej armády č. 22 | PASS  | 1 312 m     | ~16 min     |
| ZŠ Važecká č. 11              | PASS    | 1 334 m     | ~16 min     |
| ZŠ Mirka Nešpora č. 2         | PASS    | 1 769 m     | ~21 min     |
| ZŠ Bajkalská č. 29            | RISK    | 2 309 m     | ~28 min     |
| ZŠ Májové námestie č. 1       | RISK    | 2 435 m     | ~29 min     |
| ZŠ Šmeralova č. 25            | RISK    | 2 718 m     | ~33 min     |
| ZŠ Kúpeľná č. 2               | RISK    | 2 980 m     | ~36 min     |
| ZŠ Prostějovská č. 38         | FAIL    | 5 532 m     | ~66 min     |

P-b uses OSRM real walking routes (OSM SK network). Sample = 1 point (district centroid only — no address_points available, no MRK buildings in Prešov urban area). Confidence=0.3 (single sample). Note: sample_size=1 for all districts because neither address_points (0 rows) nor MRK buildings (Prešov not an MRK village) are available.

---

## 8. Branch tip

**Branch:** `feat/sprint-1-ingest`  
**Commit tip:** `565d0b2`  
*(new commit will be made after this report)*

---

## 9. Files created

```
engine/__init__.py
engine/constants.py
engine/verdict.py
engine/c_s1.py          — Š1 coverage checker (proxy, no address_points)
engine/c_s2.py          — Š2 non-overlap checker (real PostGIS)
engine/c_s3.py          — Š3 one-school-per-district checker (real PostGIS)
engine/c_pa.py          — Pa capacity (INSUFFICIENT_DATA, EDUZBER GAP)
engine/c_pb.py          — Pb walking distance (real OSRM)
engine/c_pc.py          — Pc transit (ILUSTR, Google Routes API)
engine/c_pd.py          — Pd language (INSUFFICIENT_DATA, GAP)
engine/c_pe.py          — Pe segregation signal (MRK Atlas 2019)
engine/c_pf.py          — Pf ŠVVP (NOT_EVALUATED, GAP)
engine/compose.py       — Semafor composition + gatekeeping
engine/runner.py        — Orchestrator + idempotent DB writer
tests/fixtures/__init__.py
tests/fixtures/fixture_data.py    — 7 synthetic fixtures
tests/test_engine_compose.py      — 15 pytest tests (all pass)
tests/sprint_a_report.md          — this file
```

DB migration: added unique index `verdicts_district_condition_version_idx` and `findings_district_condition_version_idx` for idempotent upserts.
