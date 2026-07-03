TASK: Skolske obvody §44 Step 2, Sprint 1 — demo input contract and engine foundation

PROJECT PATH:
/home/node/.openclaw/workspace/projects/skolske-obvody-44

ROLE:
You are Claude Code implementing a bounded coding sprint in the project repo. Work only inside the project path. Do not deploy, do not merge, do not touch credentials, and do not read F2 workspace files outside this project.

CURRENT VERIFIED STATE FROM F2:
- Branch: `feat/streets-pivot`
- Latest commit: `5366edf feat(streets-pivot): render districts as coloured streets, drop polygons, wipe findings`
- Working tree is already dirty from prior work. Do not revert or overwrite existing uncommitted changes. Inspect them, preserve them, and treat them as the current base unless they directly conflict with this sprint.
- New F2 docs to read:
  - `docs/demo-analysis-layer-article-2026-06-30.md`
  - `docs/sprint-demo-analysis/SPRINTS.md`
- Relevant prior mandate:
  - `docs/brief-streets-pivot-2026-06-28.md`

PRODUCT INTENT:
This is a demo. Real Presov VZN/address/street/geocode data must remain untouched. We add explicit demo inputs so the real engine can compute and show every important capability:
- segregation / MRK inclusion risk,
- school capacity pressure,
- long distance to assigned school,
- difficult route,
- language minority as a non-§44 prompt,
- same full address assigned to multiple districts.

HARD INVARIANTS:
- Engine is the source of truth. GUI must not invent findings, colours, severities, or demo polygons.
- Demo data is allowed only as explicit input with provenance.
- Real VZN/adresne data are not modified or distorted.
- Shared street is not a finding. Only the same full address `(street + house number)` assigned to two or more districts can count as structural overlap.
- Language is not a red §44 legal verdict. It is a non-§44 signal/podnet.
- Mock/demo must not leak into live/prod verdict mode. Enforce this with tests or construction, not only comments.

SPRINT 1 GOAL:
Create the smallest durable data + engine foundation for Step 2. Do not build the full GUI yet.

REQUIRED WORK:
1. Inspect current engine, demo input, migration, seed, view and test structure. Write findings to `docs/sprint-demo-analysis/S1_NOTES.md`.
2. Prefer extending existing demo-input patterns if they already exist. Avoid large new architecture.
3. Add or adjust minimal demo input schema/fixtures/seeds for the six scenario families above.
4. Add an engine-facing typed model/adapter or equivalent small layer that keeps real inputs and demo inputs/provenance separate.
5. Wire enough of the engine foundation that tests can prove each scenario is representable as input and has a clear path to a standard verdict/finding output.
6. Add tests for:
   - demo inputs are explicit and provenance-tagged,
   - live/prod mode cannot use demo inputs for legal verdicts,
   - same full address overlap is address-based, not street-based,
   - language remains a non-§44 signal/prompt.

OUT OF SCOPE FOR THIS SPRINT:
- Full map/register/detail UI integration.
- Playwright screenshots, except if a tiny smoke check is already required by the repo.
- New legal thresholds not already represented in the existing methodology.
- Deployment, production DB writes, or merging.

TESTS:
Run the narrowest meaningful tests first, then broader tests if changed files justify it. At minimum run the relevant Python engine tests and affected unit tests. If the full suite is too slow or blocked, document exactly what ran and what did not.

COMMIT:
If tests pass and the dirty checkout can be committed coherently, create one milestone commit with:
`Co-Authored-By: Františka 2 (CC engineer) <noreply@kpsolutions.sk>`
If pre-existing dirty state makes a clean commit unsafe, do not force it. Leave `S1_NOTES.md` with the exact diff/test status and stop.

STOP CONDITION:
Stop after Sprint 1. Report:
- changed files,
- tests run,
- whether commit was created,
- remaining risks/blockers,
- recommended Sprint 2 prompt focus.
