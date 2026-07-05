# Step 2 Sprint 1 — inventory + engine foundation notes

Scope: `docs/sprint-demo-analysis/sprint-1-prompt.md`. Source brief:
`docs/demo-analysis-layer-article-2026-06-30.md`. Base: `feat/streets-pivot`
@ `5366edf`.

## 1. What already existed (found, not built this sprint)

The streets-pivot work (commits `a068439` → `5366edf`) left a **mature demo
engine** in place, built in an earlier "demo mode" effort
(`docs/DEMO_MODE_PLAN.md`) and then partially disabled by the pivot:

- `engine/demo_inputs.py` — `get_demo_input(district_id)` loader, gated by
  `skolske_obvody.demo_mode_flag.enabled` AND a row existing in
  `skolske_obvody.district_demo_inputs`. Real-data path is untouched when
  either is false. `DEMO_CONFIDENCE`/`DEMO_COMPLETENESS` = 0.95.
- Every checker except `c_s2` (`c_s1`, `c_s3`, `c_pa`, `c_pb`, `c_pc`, `c_pd`,
  `c_pe`, `c_pf`, `c_lang`) already has a `demo = get_demo_input(...)` branch
  that returns a decisive, `is_mock=True` verdict from `district_demo_inputs`
  columns, e.g. `pa_max_distance_m`, `pf_capacity`/`pf_enrolment`,
  `pe_mrk_signal`, `pd_barrier`/`pd_barrier_kind`, `jazyk_language`.
- `engine/compose.py` — `LEGAL_CONDITIONS={S1,S2,S3}`,
  `INDICATOR_CONDITIONS={Pa,Pb,Pc,Pd}`, `SIGNAL_CONDITIONS={Pe,Pf}`. `JAZYK` is
  in **none** of these sets, so `compose_color` ignores it entirely — the
  non-§44 "podnet" contract for language was already correct.
- `engine/verdict.py` — `Verdict.is_mock`/`is_proxy`/`is_illustrative` +
  `strip_demo_tags()` (inline `[DEMO]`/"Ukážkové dáta." notices are stripped
  from stored `evidence_text`; `is_mock` still carries the flag for the UI
  banner — this is the existing "one banner, not per-row noise" mechanism).
- `engine/runner.py` — `EMIT_FINDINGS` env gate (`SO_EMIT_FINDINGS=1`), a hard
  `RedOnlyStructuralError` runtime guard (RED can only come from an S1/S2/S3
  FAIL), and stale-finding cleanup on every run.
- Tests already covering 5 of 6 scenario families end-to-end at the checker
  level: `tests/test_demo_mode.py`, `tests/test_checker_reconcile.py`,
  `tests/test_s3_demo_exclusion.py`, `tests/test_engine_compose.py`.

**Conclusion:** most of Sprint 1's nominal deliverable ("typed demo input
model", "demo inputs explicit + provenance-tagged", "prod cannot use demo for
legal verdicts") was already built. The actual gap was narrower than the
sprint prompt assumed — see §2.

## 2. What streets-pivot (`0040_streets_pivot.sql`) broke for Step 2

`0040` correctly retired the **polygon**-based Š2 overlap (`ST_Intersects`
between district geometries) and pointed `engine/c_s2.py` at
`house_geocodes` — the same full address (street + house number) in 2+
districts. That re-anchoring was already correct and untouched by this
sprint. But `0040` also:

1. Set `demo_mode_flag.enabled = false` (confirmed live: still `false`).
2. Deleted every `house_geocodes` row with `is_demo = TRUE` — including the
   "Ukážková ulica 1..8" rows, which were **the only rows that ever produced
   a genuine address-level duplicate** for the new Š2 logic.
3. Deleted the `district_overlaps`/`district_islands` demo rows (correctly —
   those were the retired polygon mechanism).

Net effect: **zero demo data exists today that can demonstrate the "same
full address in 2+ districts" scenario.** `district_demo_inputs.s2_overlap`
(a boolean column from the old polygon-demo design) is now dead — `c_s2.py`
never reads `district_demo_inputs` at all, by design (Š2 is address-level,
not per-district).

A second, more important gap: `c_s2.py`'s address-overlap query had **no
`is_demo` exclusion**. Every other checker's demo path is gated by
`demo_mode_flag` (via `get_demo_input`); `c_s3.py`'s spatial fallback path
explicitly filters `is_demo IS NOT TRUE` on `schools` (see
`tests/test_s3_demo_exclusion.py`). `c_s2.py` had neither — if a demo address
row were ever (re)seeded into `house_geocodes`, it would silently produce a
**live/prod RED** regardless of `demo_mode_flag`. That directly violates the
sprint's hard invariant: *"Mock/demo must not leak into live/prod verdict
mode. Enforce this with tests or construction, not only comments."*

## 3. Changes made this sprint

### Engine
- `engine/demo_inputs.py`:
  - Added `DistrictDemoInput` (`TypedDict`) — the engine-facing typed shape of
    a `district_demo_inputs` row (verified against the live table's actual
    columns, including `pb_minutes`/`pb_distance_m` added later by
    `0037_demo_pb_input.sql`, which had no Python-side type before).
  - Added `SCENARIO_FIELDS` — maps each of the six brief scenario families
    (`segregation_mrk`, `capacity_pressure`, `long_distance`,
    `difficult_route`, `language_minority`, `address_overlap`) to its
    condition code(s) and source table/fields. `address_overlap` is
    deliberately NOT sourced from `district_demo_inputs` (it's address-level,
    not per-district) — it points at `house_geocodes(is_demo=TRUE)`. This is
    the single source of truth Sprint 2/3 can read for register/GUI filters
    instead of re-deriving the mapping.
  - Added public `demo_mode_enabled()` wrapper (previously private
    `_demo_mode_enabled`) for checkers that gate a *real-data query*
    (include/exclude demo rows) rather than swapping in a
    `district_demo_inputs` row.
- `engine/c_s2.py`:
  - The overlap query now excludes `is_demo=TRUE` `house_geocodes` rows
    **unless** `demo_mode_enabled()` is true — by construction, so disabling
    demo mode makes Š2 blind to demo addresses no matter what is seeded.
  - When an overlap IS caused by a demo row, the query reports `any_demo` and
    the resulting `Verdict` is flagged `is_mock=True` with demo-tier
    confidence/completeness (0.95), matching every other checker's contract.
    A real address overlap (impossible in current Prešov data, but the code
    path exists) stays `is_mock=False` at confidence 0.7, unchanged.

### Demo fixture (schema/seed)
- `scripts/sql/0041_demo_s2_address_overlap.sql` (new, **not applied** — see
  §4): re-adds exactly one demo address, duplicated across Kúpeľná č. 2 and
  Sibírska č. 42 (`is_demo=TRUE`, `query_used='DEMO-s2-address-overlap-seed'`,
  idempotent delete-by-tag). This is data only — `c_s2.py`'s real query
  computes the FAIL from it; no verdict is hand-written.

### Tests (all pure-Python, no DB — mock `query_sql`)
- `tests/test_demo_input_contract.py`:
  - `SCENARIO_FIELDS` covers exactly the six brief families, each with a
    condition + fields + source.
  - `address_overlap` is not declared as `district_demo_inputs`-sourced.
  - **Construction test**: `get_demo_input()` returns `None` while
    `demo_mode_flag` is disabled, and — critically — the
    `district_demo_inputs` SELECT is never even issued (asserts `query_sql`
    call count), proving the leak can't happen structurally, not just that
    the mocked result happens to be empty.
  - `demo_mode_enabled()` mirrors the same internal gate.
  - Regression lock: `JAZYK` is in none of `LEGAL_CONDITIONS` /
    `INDICATOR_CONDITIONS` / `SIGNAL_CONDITIONS`.
- `tests/test_s2_address_overlap.py`:
  - SQL-construction assertions: the join requires `house_number` equality
    (not just `street`) — the address-vs-street distinction is enforced, not
    just documented.
  - SQL-construction assertions: `is_demo IS NOT TRUE` is present when demo
    mode is off, absent when it's on.
  - Behavioural: no rows → PASS; real-caused FAIL → `is_mock=False`,
    confidence 0.7; demo-caused FAIL → `is_mock=True`, confidence ≥ 0.90,
    `provenance.demo=True`; demo tag stripped from stored `evidence_text`.

## 4. Explicitly NOT done (deferred / out of scope)

- **`0041_demo_s2_address_overlap.sql` was written but NOT executed against
  the live Supabase DB.** The sprint prompt lists "production DB writes" as
  out of scope for Sprint 1. All DB interaction this sprint was read-only
  (`SELECT`s to verify live schema/state, listed below). Applying `0041` and
  flipping `demo_mode_flag.enabled=true` is a one-line Sprint 2 action:
  `python3 scripts/apply_sql.py scripts/sql/0041_demo_s2_address_overlap.sql`.
- `python3 -m engine.runner` was **not run** against the live DB this sprint
  (it always writes verdicts, which is also a production DB write). The
  runner's own idempotent UPSERT design means this is safe to run in Sprint 2
  once `0041` is applied and demo mode is re-enabled.
- No GUI/map/register work (`lib/compliance/step1.ts`, the modified
  `app/*.tsx` files, `summary-strip.tsx`) — those are pre-existing uncommitted
  changes from prior work, preserved as-is, not touched by this sprint.
- No new legal thresholds — Pb's existing 2 km / 30 min / 4 km constants
  (`engine/constants.py`) are unchanged.

## 5. Live DB read-only checks performed (informational only, no writes)

- `demo_mode_flag`: 1 row, `enabled=false` (confirmed streets-pivot's state).
- `house_geocodes WHERE is_demo=true`: 0 rows (confirms the gap in §2).
- Real address-overlap sanity query (the same join `c_s2.py` uses, minus the
  `is_demo` filter): 0 rows — real Prešov data has no address overlaps by
  construction.
- `district_demo_inputs`: 12 rows (one per Prešov district, from the
  pre-pivot seed), columns match `DistrictDemoInput` including the later
  `pb_minutes`/`pb_distance_m` addition.
- Kúpeľná č. 2 / Sibírska č. 42: both `school_type='ZS'`,
  `teaching_language='SK'`, `geom IS NOT NULL` — valid target pair for
  `0041`'s demo address (same-type filter in `c_s2.py` will match them).

## 6. Test run

```
$ python3 -m pytest tests/ -q
66 passed, 3 warnings in <1s
```

52 pre-existing + 14 new (`test_demo_input_contract.py` ×7,
`test_s2_address_overlap.py` ×7). No test was skipped or modified. Warnings
are pre-existing (`test_topology.py` returns instead of asserting — not
touched this sprint, would need its own decision to fix).

`npm run build` / `npm run lint` / vitest were **not run** — no TypeScript
file was touched this sprint (only `engine/*.py`, `tests/*.py`,
`scripts/sql/*.sql`, `docs/*.md`). The pre-existing dirty `.tsx`/`.ts` files
are untouched and were dirty before this sprint started.

## 7. Recommended Sprint 2 focus

1. Apply `0041_demo_s2_address_overlap.sql`, flip `demo_mode_flag.enabled =
   true`, run `python3 -m engine.runner` (with `SO_EMIT_FINDINGS=1`) and
   confirm: exactly one S2 FAIL pair (Kúpeľná ↔ Sibírska), `is_mock=True`,
   and `RedOnlyStructuralError` does NOT fire (S2 FAIL is a legal condition,
   so RED is legitimate here — worth asserting explicitly in a Sprint 2 test).
2. Decide Pb's relationship to Pa in the GUI/register filter taxonomy — both
   now live under `SCENARIO_FIELDS["long_distance"]`; Sprint 2 should confirm
   whether the register needs to distinguish "air-line distance" (Pa) from
   "walking time" (Pb) as separate filter facets or present them together.
3. Re-verify `EMIT_FINDINGS`/`SHOW_COMPLIANCE` gates end to end once findings
   are re-enabled — `lib/compliance/step1.ts` currently hard-disables all
   compliance display; Sprint 3 (GUI) needs a coordinated flip of both the
   engine-side (`SO_EMIT_FINDINGS`) and GUI-side (`NEXT_PUBLIC_SO_SHOW_COMPLIANCE`)
   flags, not just one.
4. `test_topology.py`'s three tests return dicts instead of asserting
   (pytest warning) — low priority cleanup, not blocking.
