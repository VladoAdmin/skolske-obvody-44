# Finding Verification Report — § 44 školské obvody (Prešov, 12 obvodov)

**Date:** 2026-06-27
**Verifier of correctness verdicts:** OpenAI **GPT-5.5** (`gpt-5.5-2026-04-23`) — confirmed on all 13 calls (12 per-district + 1 mismatch triage). Every response carried `model: gpt-5.5-2026-04-23`; no call fell back to Claude, no fabricated/non-gpt5.5 answer was accepted.
**Grounding:** all numbers below come from live Supabase PostgREST views (`so_findings_panel`, `so_district_scorecard`, `so_district_compositions`, `so_register_mismatches`, `so_district_address_stats`, `so_mock_indicators`, `so_finding_explanations`) plus the two display-layer source files. GPT-5.5 cost for this audit: ~$1.58.

---

## 1. Overall trust verdict

**The 224 real findings are individually plausible but the portal has a systemic integrity defect: two layers — the legal scorecard (`so_district_scorecard`) and the findings panel (`so_findings_panel`) — disagree with each other about the same legal axis for the same district, in every one of the 12 districts.** The scorecard reports **S2 = PASS in all 12 districts** ("0 prekryvov nad toleranciou 1.0 m²") while the findings panel simultaneously shows **open critical S2 FAILs** ("FAIL: 9–11 prekryvov, tens of millions of m²") in those same 12 districts. The same scorecard-PASS-vs-findings-FAIL contradiction occurs for **S3 in 6 districts** and **Pb in 7 districts**. GPT-5.5 rated **all 12 districts MAJOR_ISSUES** primarily for this reason. This is exactly the class of "the card says one thing, the map/panel shows another" that prompted the audit — it is real, not a misread.

A second, independent defect is that the **Pa label/content-mismatch pattern recurs in the AI-explanation layer**: the canonical AI explanations are attached by `(condition_code, severity)` and therefore land on findings whose *evidence* says the opposite (S3 "viac ako jedna škola" glued onto evidence reading "0 verejných škôl"; Pb "prekračuje 30 min" glued onto evidence reading 26 min / under the limit; Pe "v súlade" glued onto a risk signal; S1 "mapa adries… nie je v súlade" glued onto "Register adries nedostupný / bez adresných bodov"). 28 such AI-text mismatches across the 12 districts.

**On the address question that triggered the audit: of the 118 `register_mismatches`, GPT-5.5 judged ZERO to be real geocoding/assignment errors — 91 are legitimate house-number range-splits and 27 are UNCERTAIN (single-address, insufficient data to decide, never positively wrong).** So there is **no confirmed real address error** in the register-mismatch set. The owner's "red route points into another district" effect is a **display artifact**, not a bad geocode: for codes {Pa,Pb,Pc,Pd} the red dashed line is drawn from the **district polygon centroid → school marker** (`components/region-map.client.tsx:209`, popup literally reads "Centroid obvodu → škola"), and the centroid can sit visually inside a neighbouring coloured polygon.

Net: **trust the individual address geocoding; do not trust the scorecard-vs-panel agreement or the AI explanation wording until the two engines are reconciled and explanations are bound to evidence, not to severity.**

---

## 2. Per-district table (GPT-5.5 axis judgments)

Axes: (1) address read from VZN, (2) geocode/placement, (3) evaluation/engine logic & internal consistency, (4) display (label↔content, AI text, route). `OK` = GPT-5.5 found the axis sound; `X` = GPT-5.5 flagged a defect on that axis. "# findings" = rows in `so_findings_panel`.

| District | Verdict | # findings | A1 addr | A2 geo | A3 eval | A4 display | GPT overall | # defects | reg. mismatches |
|---|---|---|---|---|---|---|---|---|---|
| Základná škola s materskou školou, Nám. kráľovnej pokoja | RED | 19 | OK | X | X | X | MAJOR_ISSUES | 10 | 3 |
| Základná škola, Bajkalská č. 29 | ORANGE | 18 | OK | X | X | X | MAJOR_ISSUES | 14 | 45 |
| Základná škola, Československej armády | RED | 21 | OK | X | X | X | MAJOR_ISSUES | 14 | 6 |
| Základná škola, Kúpeľná č. 2 | RED | 23 | X | X | X | X | MAJOR_ISSUES | 13 | 2 |
| Základná škola, Lesnícka č. 1 | ORANGE | 17 | OK | X | X | X | MAJOR_ISSUES | 13 | 3 |
| Základná škola, Májové námestie č. 1 | ORANGE | 17 | OK | X | X | X | MAJOR_ISSUES | 13 | 1 |
| Základná škola, Mirka Nešpora č. 2 *(demo Pa card here)* | ORANGE | 19 | OK | OK | X | X | MAJOR_ISSUES | 19 | 0 |
| Základná škola, Prostějovská č. 38 | RED | 21 | OK | X | X | X | MAJOR_ISSUES | 16 | 2 |
| Základná škola, Sibírska č. 42 | ORANGE | 17 | OK | X | X | X | MAJOR_ISSUES | 11 | 5 |
| Základná škola, Šmeralova č. 25 | ORANGE | 21 | OK | X | X | X | MAJOR_ISSUES | 15 | 49 |
| Základná škola, Šrobárova č. 20 | ORANGE | 15 | OK | X | X | X | MAJOR_ISSUES | 13 | 2 |
| Základná škola, Važecká č. 11 | ORANGE | 17 | OK | OK | X | X | MAJOR_ISSUES | 9 | 0 |
| **Totals** | 4 RED / 8 ORANGE | **225** (224 real + 1 demo) | 11 OK / 1 X | 10 X | **12 X** | **12 X** | 12× MAJOR | 160 | 118 |

Notes: A1 (address-read) is sound in 11/12 — only Kúpeľná drew an address-read flag, and that flag is really about the register-mismatch placement (Na Rovni / Školská), i.e. an A2 concern, not a misread VZN. A2 is `OK` only for the two districts with zero register mismatches (Mirka Nešpora, Važecká). A3 and A4 fail in all 12 — driven almost entirely by the two systemic defects below, not by 12 unrelated bugs.

---

## 3. Prioritized defect list

Each defect is tagged **[REAL ERROR]** (genuine logic/data fault), **[DISPLAY-ONLY]** (data is right, presentation misleads), **[DEMO-DATA]** (illustrative/mock, correctly quarantined), or **[LEGIT]** (looks like an error but is lawful/expected).

### D1 — [REAL ERROR] Scorecard ⇄ findings-panel disagree on the same legal axis — **all 12 districts**
The legal verdict layer and the findings layer are computed by different logic and contradict each other:
- **S2:** scorecard `value='PASS'` ("0 prekryvov… nad toleranciou 1.0 m²") in **12/12 districts**, while `so_findings_panel` carries open **critical** S2 "FAIL: 9–11 prekryvov" with overlap areas of 2.7M–56.7M m². (12/12)
- **S3:** scorecard `PASS` ("1 verejná škola, FK v geometrii: True") while findings show critical "FAIL: 2–10 škôl" — **6 districts** (Bajkalská, Lesnícka, Mirka Nešpora, Sibírska, Šmeralova, Važecká).
- **Pb:** scorecard `PASS` (~1.9 km / ~23 min) while findings show critical "FAIL" up to 16–17 km / 165–194 min — **7 districts**.

Evidence: e.g. Lesnícka — `so_district_scorecard` S2 `value=PASS` evidence "0 prekryvov s inými obvodmi typu ZS/SK nad toleranciou 1.0 m²" vs `so_findings_panel` S2 critical "FAIL: 9 prekryv(ov)… 27 198 054.6 m²" (both `status=open`, `is_demo=false`). This is the audit's top finding. Either the findings panel is showing stale/looser-threshold computations that the scorecard already superseded, or the scorecard is masking real failures — **they cannot both be authoritative**. Engine fields: `so_district_compositions.engine_version` / `methodology_version` should be checked against the engine that produced the panel rows. Fix is a data/engine reconciliation, not a display tweak.

### D2 — [DISPLAY-ONLY] AI explanations bound to `(code, severity)` instead of to the finding's evidence — recurrence of the Pa label/content pattern (28 instances)
`so_finding_explanations` keys on `(condition_code, severity)`, so one canned text is reused for findings whose evidence contradicts it:
- **S3 critical:** the explanation says "v danom školskom obvode sú evidované **viac ako jedna** verejná škola", but **5 of the S3 critical findings** have evidence "FAIL: **0** verejných škôl typu ZS priestorovo v obvode" (the opposite case — the assigned school's geometry doesn't cover it). Districts: Nám. kráľovnej pokoja, Československej armády, Sibírska, Šrobárova/Kúpeľná set.
- **Pb high:** explanation "presahuje… 30 minút (cca 2,5 km)" attached to evidence reading 26.0–28.1 min / ~2.1–2.3 km (under the limit) in several districts.
- **Pe medium:** explanation "obvod nevylučuje deti… v súlade s §44" attached to a finding the panel frames as a **risk SIGNAL** (MRK area > threshold) — reads as compliant when the signal is a flag.
- **S1 medium:** explanation "mapa adries všetkých žiakov… nie je v súlade so správnym obvodom" attached to evidence that only says "PROXY / bez adresných bodov / Register adries nedostupný" — overstates a data-gap as a compliance failure.
- **School-name leak:** Pb explanation for **Prostějovská č. 38** names "Základná škola Vladimíra Nešpora" (wrong school). See D4.

This is the same defect class as the known Pa demo card (label "Vzdialenosť" over capacity evidence). Tagged DISPLAY-ONLY because the *evidence numbers* are right; the *explanation prose* is mismatched. Fix: bind explanations to the actual finding/evidence, or add the missing severity/sub-case variants (esp. the S3 "0 schools" case).

### D3 — [LEGIT] (with a [REAL ERROR] tail) — the 118 register mismatches
GPT-5.5 triage (with house-number context the per-district calls lacked) — **see §4**: **0 REAL, 91 LEGIT, 27 UNCERTAIN.** The 88 Sabinovská rows (44 under Bajkalská-VZN + 44 under Šmeralova-VZN, all landing in the Prostějovská polygon) are a textbook range-split: the **identical** súpisné-number set is assigned to two VZN districts, proving the register lacks orientačné-number granularity to resolve a lawful split — **LEGIT**, not a geocode error. The 27 singletons (Čergovská, Astrová, Na Rovni, Tichá, Višňová, …) are **UNCERTAIN** only because a single address gives no split pattern or boundary-distance to decide; none was positively wrong. NB: the per-district GPT calls tagged these 16× as `REAL_ERROR` because they saw a mismatch without the range-split context — the dedicated triage supersedes that, and **the authoritative count of real address errors is 0.**

### D4 — [REAL ERROR] School-identity mismatch on Prostějovská č. 38
`so_findings_panel` Pb evidence for district "Základná škola, **Prostějovská č. 38**" reads "Škola: Základná škola **Vladimíra Nešpora**" — a different school — and the Pb numbers there are internally inconsistent too (scorecard 1946 m / 23.4 min PASS vs findings 5532 m and 16182 m FAIL). Evidence: `so_district_scorecard` + `so_findings_panel` rows for that district. Looks like a wrong FK/school-name join on the distance computation for this district. (1 district.)

### D5 — [REAL ERROR] S1 "Register nedostupný" contradicts the data the portal now has — 4 districts
S1 scorecard/finding evidence still says "**Register adries — momentálne nedostupný / bez adresných bodov**", but `so_district_address_stats` now carries register-derived clean address counts and `so_register_mismatches` exists for those same districts (e.g. Šmeralova: 575 clean habitable addresses; Bajkalská, Šrobárova, Kúpeľná similar). The S1 narrative is stale relative to the address pipeline that landed on 2026-06-26/27. Tagged REAL ERROR (contradictory state), though it is principled that **true S1 stays NEÚPLNÉ** — the register is buildings/addresses, not pupil→school enrolment. Fix the wording to "we now have addresses but still no pupil register", don't claim the register is unavailable.

### D6 — [DISPLAY-ONLY] Centroid→school red route reads as an address→school route (the original complaint)
`components/findings-panel.tsx:57` defines `DISTANCE_CODES = {Pa,Pb,Pc,Pd}`; `:78–104` dispatches a route whose `from` = `district_geom_centroid_lat/lon` (polygon centroid), `to` = school marker. `components/region-map.client.tsx:188–223` draws the red dashed line and the popup says "Centroid obvodu → škola". The centroid is **not** a geocoded pupil address, so for any district where the centroid sits inside a neighbour's coloured polygon the line "points into another district". Data is correct; the visual implies a meaningful address-distance it isn't. Fix: relabel, or draw from a representative in-district address point, or suppress the line for Pc/Pd.

### D7 — [DEMO-DATA] Mock secondary indicators (Pa/Pc/Pd/Pf) — correctly quarantined, with one cosmetic leak risk
`so_mock_indicators` (Pa/Pc/Pd/Pf × 12) is flagged `is_demo=true`; the scorecard rows for these codes carry `is_mock=true` (Pf), `is_illustrative=true` (Pc) or `is_proxy=true` (Pa/Pd), and GPT-5.5 confirmed **"no clear leak into the legal verdict"** in every district. `so_district_compositions` (the verdict source) does not reference mock. **Benign.** Two caveats: (a) the **Pa demo card** itself (`is_demo=true`, district Mirka Nešpora) is still an *open medium finding* and carries the known three-way conflict — label "Vzdialenosť ≤ 2 km" / evidence "412 detí vs kapacita 360" / mock "79 % obsadenosť, kapacita 520/480"; keep it visibly separated from real legal findings. (b) Pa is `is_proxy` in the scorecard but `is_demo` in the finding — make the demo flag consistent across both layers.

### D8 — [DISPLAY-ONLY] S2 multipart-geometry findings get a generic gap/overlap explanation — 6 instances
Some S2 findings are "obvod sa skladá z N oddelených častí" (disconnected polygon), but the attached S2 explanation talks generically about gaps/overlaps. Cosmetic subset of D2.

---

## 4. Register mismatch triage (GPT-5.5, authoritative count)

Input: all 118 `so_register_mismatches` rows, grouped into 32 (ulica, vzn_district, poly_district) groups with súpisné-number ranges, judged by GPT-5.5 (`gpt-5.5-2026-04-23`) with explicit range-split context.

| Label | Address count | What |
|---|---|---|
| **REAL** (genuine geocode/assignment error) | **0** | None. GPT-5.5 found no address it could positively call wrong. |
| **LEGIT** (lawful range-split / boundary) | **91** | 88 Sabinovská (44 Bajkalská-VZN + 44 Šmeralova-VZN → Prostějovská polygon; identical súpisné set under two VZN districts = missing orientačné granularity for a lawful split) + 3 Tomášikova. |
| **UNCERTAIN** (single address, insufficient data) | **27** | Isolated singletons (Čergovská, Astrová, Duklianska, Na Rovni, Školská, Tichá, Višňová, Ortáš, …). Each lacks a split pattern or boundary-distance, so neither REAL nor LEGIT can be proven. |
| **Total** | **118** | |

GPT-5.5 summary note (verbatim gist): "Sabinovská and Tomášikova show the explicit same-street/same-house-number multi-VZN pattern indicating missing orientačné granularity for legal splits; the remaining singletons lack enough split or boundary-distance evidence to decide."

**Bottom line for the owner: 0 of 118 register mismatches are confirmed real address errors.** The 27 UNCERTAIN are worth a targeted second geocoding pass (precise orientačné numbers + boundary-distance) to settle, but none is presently a known bad geocode.

---

## 5. Defect counts by tag (across all 12 districts)

GPT-5.5 emitted 160 per-district defect items; de-duplicated into 8 themes:

| Tag | Distinct defects | Notes |
|---|---|---|
| [REAL ERROR] | **D1 (12-district scorecard⇄findings) + D4 (1) + D5 (4)** | D1 is the systemic one; register-mismatch "REAL_ERROR" tags from per-district calls are **superseded** by the triage (→ 0 real). |
| [DISPLAY-ONLY] | **D2 (28 AI-text) + D6 (route) + D8 (6 multipart)** | Presentation, not data. |
| [DEMO-DATA] | **D7 (9, benign)** | Mock correctly quarantined; no verdict leak. |
| [LEGIT] | **D3 → 91 addresses** | Range-splits. |
| UNCERTAIN | **27 addresses** | Need a second geocoding pass. |

Raw GPT-5.5 per-district `defects[].kind` tally (before triage supersedes the register subset): REAL_ERROR 43, DISPLAY_ONLY 95, LEGIT 13, DEMO_DATA 9. After applying the authoritative triage to the register subset, the register portion of those 43 REAL_ERRORs (16 items / 118 addresses) collapses to **0 real address errors**, leaving the REAL_ERROR weight concentrated in D1/D4/D5 (engine & join integrity), not in geocoding.

---

## 6. Method & guardrails

- **GPT-5.5 authenticity:** confirmed `model: gpt-5.5-2026-04-23` on all 13 calls (a PONG probe first, then per-call assert that `r.model` starts with `gpt-5.5`; the run was coded to `sys.exit` on any mismatch). No Claude judgment was substituted for GPT-5.5's. The triage's first attempt returned empty content because GPT-5.5's reasoning tokens exhausted a 4k budget; re-run at 9k tokens succeeded (finish_reason=stop, 2464 reasoning tokens) — a budget issue, not a fabrication.
- **Claude's role:** assembled the grounded bundles, verified GPT-5.5's structural claims against the raw views and the two display source files (e.g. confirmed the scorecard⇄findings contradiction and the centroid-route code independently), and applied the dedicated triage as the authoritative answer over the context-blind per-district register tags. Claude did **not** author the correctness verdicts.
- **Every number** in §1–§5 traces to a live view query or a source line cited inline.

### Source references
- Scorecard⇄findings contradiction: `so_district_scorecard` vs `so_findings_panel` (per-code `value` vs `evidence_public_text`, `status='open'`, `is_demo=false`).
- AI-text mismatch: `so_finding_explanations` keyed on `(condition_code, severity)`.
- Register mismatches: `so_register_mismatches` (118 rows).
- Mock quarantine: `so_mock_indicators` (`is_demo`), scorecard flags `is_mock`/`is_illustrative`/`is_proxy`, verdict view `so_district_compositions` (no mock reference).
- Centroid route: `components/findings-panel.tsx:57,78-104`; `components/region-map.client.tsx:188-223`.
- Canonical labels: `lib/compliance/labels.ts:5-12`.
