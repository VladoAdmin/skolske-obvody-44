# Step 2 Sprint 2 — engine verdicts + findings for the six demo scenarios

Scope: `docs/sprint-demo-analysis/sprint-2-prompt.md` / `SPRINTS.md` §Sprint 2.
Base: `feat/streets-pivot` @ `f169333` (Sprint 1). Linear: VLA-6.

## 1. Required fixes from the Sprint 1 GPT-5.5 review (done first)

1. **`scripts/sql/0041_demo_s2_address_overlap.sql`** — added a `DO $$ ... $$`
   pre-INSERT validation block: `RAISE EXCEPTION` if the two named target
   districts (Kúpeľná č. 2 / Sibírska č. 42) don't both exist, or don't both
   carry `school_type='ZS' AND teaching_language='SK'`. Previously a rename or
   attribute drift would silently insert 0/1 rows (a misleading half-seeded
   demo) instead of failing loudly.
   - While applying the fixed script, also found and fixed a **pre-existing
     unrelated bug**: `ST_GeneratePoints(d.geom, 1, 4242 + pair.rn)` passed a
     `bigint` seed (from `row_number()`), but PostGIS's signature wants
     `integer` → `function ... does not exist`. Cast to `::integer`. Not part
     of the review's ask, but blocked applying the migration at all.
2. **`engine/demo_inputs.py`** — renamed `reset_cache()` → `refresh_demo_mode()`
   (all call sites updated: `engine/runner.py`, `tests/test_demo_input_contract.py`).
   Added a comment above `_demo_mode_enabled()`'s `@lru_cache` documenting the
   one-shot-process assumption explicitly: safe only because
   `engine/runner.py` is a one-shot CLI that calls `refresh_demo_mode()` once
   at the start of `run()`; a long-lived process would need to call it again
   per unit of work.
3. **`engine/c_s2.py`** — added a comment on the `lang_filter` f-string
   documenting `school_type`/`teaching_language` interpolation as
   internal-trusted-only (sourced from `districts`, ingested from WFS/VZN,
   never end-user input). Not refactored, per the review's explicit scope.

## 2. Migration applied + demo mode enabled + runner executed

```
$ python3 scripts/apply_sql.py scripts/sql/0041_demo_s2_address_overlap.sql
[apply_sql] OK on 0041_demo_s2_address_overlap.sql: {'ok': True}
```

Seeded exactly 2 `house_geocodes` rows (`is_demo=TRUE`,
`query_used='DEMO-s2-address-overlap-seed'`), one inside each of Kúpeľná č. 2
and Sibírska č. 42, same street + house number.

`demo_mode_flag.enabled` flipped `false → true` for the Prešov municipality row.

```
$ SO_EMIT_FINDINGS=1 python3 -m engine.runner
...
Verdicts written: 120
Findings written: 11
Stale findings deleted: 0
```

No `RedOnlyStructuralError` raised. Verdict value distribution across all 120
rows: `PASS=98, FAIL=7, SIGNAL=3, NO_SIGNAL=11, RISK=1` (INSUFFICIENT_DATA/
NOT_EVALUATED/INCOMPLETE all absent — every condition is decisively evaluated
under demo mode, per the demo contract).

### S2 address-overlap verification (the Sprint 1 → Sprint 2 handoff item)

Both target districts: `S2=FAIL`, `is_mock=True`, `confidence=0.95`,
`data_completeness=0.95`, `provenance.demo=True`,
`provenance.overlap_partners` pointing at each other, `shared_addresses=1`.
Evidence text has the `Ukážkové dáta.` tag stripped in the stored record (only
`is_mock` carries the flag; no inline demo tag reaches the DB/UI text).

Districts colour `RED`, and `_assert_red_only_structural` confirmed this is
legitimate (S2 ∈ LEGAL_CONDITIONS) — no exception raised for either district.

## 3. All six scenario families now compute end to end into verdict + finding

| # | Scenario (brief)        | Condition(s) | Sample run result (demo mode ON)                                   |
|---|--------------------------|--------------|----------------------------------------------------------------------|
| 1 | MRK / segregation risk   | Pe           | Šrobárova: `SIGNAL`, finding severity `medium`, never enters semafor |
| 2 | Capacity pressure        | Pf           | Sibírska: `SIGNAL` (712 > 560 cap.), severity `medium`, signal-only  |
| 3 | Long distance            | Pa / Pb      | Bajkalská: `Pa=FAIL` (2480 m); Lesnícka: `Pb=RISK` (2900 m/38 min)   |
| 4 | Difficult route          | Pc / Pd      | Lesnícka: `Pc=FAIL` (2 prestupy); Šmeralova-area demo: `Pd=FAIL`     |
| 5 | Language minority        | JAZYK        | Važecká: `SIGNAL` (HU), severity `low`, outside semafor, never RED   |
| 6 | Same full address overlap| S2           | Kúpeľná ↔ Sibírska: `FAIL`, `is_mock=True`, drives legitimate RED    |

Each of the 9 checkers (`c_s1`…`c_pf`, `c_lang`) already had a `get_demo_input`
/ `demo_mode_enabled` branch built in earlier work (see `S1_NOTES.md` §1) —
Sprint 2's job was to prove the whole pipeline actually runs against a live
demo-enabled DB end to end, close the review gaps, and tighten the findings
severity discipline (see §4). No checker logic beyond severity mapping was
changed.

## 4. Severity discipline — findings-level fix (new this sprint)

`engine/runner.py::_write_finding` previously mapped severity purely by
verdict *value* (`FAIL → "critical"` for every condition), which meant an
indicator FAIL (Pa/Pb/Pc/Pd) looked exactly as severe as a legal S1/S2/S3
FAIL in the findings register — undermining the "risk indicators max ORANGE"
discipline at the findings level even though `compose_color`'s semafor logic
was already correct. Fixed to be condition-group aware:

- `LEGAL_CONDITIONS` (S1/S2/S3): `FAIL → critical`, `INCOMPLETE → medium`.
- `INDICATOR_CONDITIONS` (Pa–Pd): `FAIL/RISK → high` (never `critical`),
  `INSUFFICIENT_DATA → low`.
- `SIGNAL_CONDITIONS` (Pe/Pf): `SIGNAL → medium`.
- `JAZYK`: `SIGNAL → low` (podnet nad rámec § 44 — must never be `critical`
  or `high`, matching "language never red").

Verified against the live run:
```
S1/S2/S3  → critical
Pa/Pb/Pc/Pd → high
Pe/Pf     → medium
JAZYK     → low
```

## 5. Tests

New file `tests/test_runner_guards.py` (9 tests):
- `_assert_red_only_structural`: S2-demo-driven RED does NOT raise (legitimate
  legal FAIL); RED with no S1/S2/S3 FAIL DOES raise; a non-structural FAIL
  (synthetic JAZYK=FAIL) riding alongside a real S1 FAIL DOES raise.
- `_write_finding` severity tiers: legal FAIL=`critical`; indicator FAIL/RISK
  (Pa/Pd/Pb)=`high` (never `critical`); signal (Pe/Pf)=`medium`; JAZYK=`low`.
  Each of these tests fails if severity discipline regresses.
- `refresh_demo_mode()`: proves the lru_cache is genuinely stale until
  refreshed (first read cached, mid-test DB value flip invisible without a
  `refresh_demo_mode()` call, visible immediately after).

`tests/test_demo_input_contract.py` updated in place (7 call sites) for the
`reset_cache` → `refresh_demo_mode` rename; no test logic changed.

```
$ python3 -m pytest tests/ -q
75 passed, 3 warnings in <1s
```

75 = 66 pre-existing (Sprint 1 baseline) + 9 new. No test skipped or modified
beyond the rename. Warnings are pre-existing (`test_topology.py` returns
instead of asserting — flagged in S1_NOTES §7, still not touched, still not
blocking).

`npm run build` / `npm run lint` / vitest were **not run** — no TypeScript
file was touched this sprint (only `engine/*.py`, `tests/*.py`,
`scripts/sql/0041_*.sql`, `docs/*.md`).

## 6. Live DB state after this sprint (informational)

- `demo_mode_flag.enabled = TRUE` for the Prešov municipality (was `false`
  before this sprint — flipped per the sprint's own instruction to enable
  demo mode and run the engine end to end).
- `house_geocodes`: 2 new `is_demo=TRUE` rows (the 0041 seed); no real rows
  touched.
- `verdicts`: 120 rows written this run (engine_version-scoped upsert; prior
  engine_version rows purged by `_purge_other_versions`, per existing runner
  behaviour, unrelated to this sprint).
- `findings`: 11 rows written (one per non-clean condition per district,
  `SO_EMIT_FINDINGS=1`), all correctly `is_demo=TRUE`-tagged and severity-tiered
  per §4.

Note: with demo mode ON, S1/S3 real-data paths for non-demo districts also
became fully decisive (all 12 districts have a `district_demo_inputs` row from
the pre-pivot seed — see S1_NOTES §5), which is why the FAIL/SIGNAL/RISK
counts above look broader than "just the one S2 pair" — that is expected: the
demo dataset covers every district, not only the two address-overlap ones.

## 7. Explicitly NOT done (deferred / out of scope)

- No map/register UI work (Sprint 3).
- No new legal thresholds — `engine/constants.py` unchanged.
- No deploy, no merge, no credentials touched.
- Pb vs Pa register-filter taxonomy question (S1_NOTES §7 item 2) — still
  open, deferred to Sprint 3 (GUI/register scope).
- `test_topology.py` warning cleanup — still deferred, low priority.
