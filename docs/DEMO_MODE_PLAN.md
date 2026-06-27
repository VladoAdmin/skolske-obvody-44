# Demo Mode — full-data decisive demo (feat/demo-mode)

Goal: every district × every §44 condition = DECISIVE (PASS/FAIL/RISK/SIGNAL),
confidence ≥0.90 + completeness ≥0.90, all DEMO-flagged at INPUT level, engine
recomputes, views consistent. JAZYK never in semafor.

## Mechanism
New table `skolske_obvody.district_demo_inputs` — one row per district carrying
complete demo input for the conditions that otherwise bail. A global flag
`demo_mode` (engine reads it); when a district has a demo-input row, each checker
computes a real verdict from it at conf/compl ≥0.90, flagged is_mock=TRUE.
Real-data path unchanged (no demo row → honest INSUFFICIENT_DATA/INCOMPLETE).

Conditions reworked to read demo input:
- S1: demo `s1_uncovered`, `s1_multi` counts → PASS or FAIL (wrong-district address).
- S2: demo overlap layer (existing district_overlaps.is_demo) → FAIL for the two
      partners; else PASS. High conf in demo mode.
- S3: demo `s3_school_count` → PASS(1)/FAIL(2). (real spatial count still honest off-demo)
- Pa: demo far address in house_geocodes (is_demo) → FAIL; else PASS from real/seed.
- Pb: real OSRM (already decisive PASS/RISK/FAIL). Demo nudge not needed.
- Pc: demo `pc_transfers` (0/1 → PASS, ≥2 → FAIL). Pc becomes a decisive §44
      indicator in demo mode (still flagged DEMO), no Google API dependency.
- Pd: demo `pd_barrier` bool → FAIL (busy road/rail w/o crossing) / PASS.
- Pe: demo MRK buildings (existing) → SIGNAL; else NO_SIGNAL needs Atlas ctx.
      In demo mode every district gets a decisive Pe (SIGNAL where seeded, else
      PASS-equivalent NO_SIGNAL with high conf).
- Pf: demo capacity+enrolment → SIGNAL(over)/NO_SIGNAL(under), high conf.
- JAZYK: demo teaching_language (existing). Outside semafor.

NOTE: Pe/Pf are SIGNAL_CONDITIONS. "Decisive" for them = SIGNAL or NO_SIGNAL
(NOT NOT_EVALUATED). Both are non-INCOMPLETE/decisive states.

## Distribution (12 districts)
GREEN (all legal PASS, no risk indicator): Námestie, Májové, Prostějovská, Mirka Nešpora, Šrobárova*(Pe signal only, signals don't degrade), Important: Šrobárova has Pe SIGNAL but Pe is signal-panel → stays GREEN legally. Use Šrobárova as GREEN-with-signal.
RED (≥1 legal FAIL): Bajkalská (S1+Pa), Kúpeľná (S2), Sibírska (S2+Pf signal), Šmeralova (S3), Lesnícka (Pc fail→ only indicator→ORANGE not RED), Československej (Pd→indicator→ORANGE).

Refined:
- Bajkalská: S1 FAIL (wrong-district addr) + Pa FAIL (>2km)  → RED
- Kúpeľná:   S2 FAIL (overlap w/ Sibírska)                    → RED
- Sibírska:  S2 FAIL (overlap) + Pf SIGNAL (overcrowd)        → RED
- Šmeralova: S3 FAIL (2 schools)                              → RED
- Lesnícka:  Pc FAIL (≥2 transfers) [indicator]              → ORANGE
- Československej: Pd FAIL (barrier) [indicator]             → ORANGE
- Šrobárova: Pe SIGNAL (MRK) [signal panel only]            → GREEN
- Važecká:   JAZYK podnet (outside §44)                      → GREEN
- Námestie, Májové, Prostějovská, Mirka Nešpora: all PASS    → GREEN

Result: 4 RED, 2 ORANGE, 6 GREEN. Realistic spread. Every violation type ≥1.

## Confidence in demo mode
Each checker: when verdict derived from complete demo input → confidence=0.95,
data_completeness=0.95. Real-data verdicts keep their honest lower numbers, but
in demo mode EVERY district has demo input so every verdict is ≥0.90.

## Idempotency
0036 migration: create table + per-district seed (TRUNCATE+INSERT). Engine
upserts on (district_id, condition_code, engine_version). One clean run.
