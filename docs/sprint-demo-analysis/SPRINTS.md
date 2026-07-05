# Step 2 demo analysis layer — sprint plan

Source brief: `docs/demo-analysis-layer-article-2026-06-30.md`.
Current base: branch `feat/streets-pivot`, after Step 1 streets pivot.

## Invariants

- Real VZN, address, street and geocode data stay unchanged.
- Demo/mock inputs are explicit inputs, never hidden UI hardcodes.
- Engine remains the source of truth for verdicts, findings, colours and evidence.
- GUI renders only engine/data outputs.
- Shared street is not a finding. Only the same full address assigned to multiple districts can become a structural overlap.
- Language is a non-§44 signal/prompt, not a red legal verdict.
- Demo provenance must be visible in evidence without cluttering every row.

## Sprint 1 — data contract and engine foundation

Goal: add the smallest durable demo input contract and wire it into the engine layer enough that tests can prove every demo scenario is representable without GUI shortcuts.

Deliverables:

- Inventory of existing demo inputs, engine checks and read views in `docs/sprint-demo-analysis/S1_NOTES.md`.
- Minimal schema/fixture changes for demo scenarios:
  - MRK/segregation or inclusion risk,
  - capacity pressure,
  - long distance,
  - difficult route,
  - language minority outside §44,
  - same full address overlap.
- Engine-facing typed input model or adapter that keeps real data and demo data provenance separate.
- Tests proving demo inputs are explicit and cannot leak into live/prod verdict mode.
- A milestone commit or a clear reason why commit is deferred because the checkout already had uncommitted state.

Out of scope:

- Full map/register UI.
- New legal thresholds not already supported by the existing methodology.
- Deploy or merge.

## Sprint 2 — engine verdicts and findings

Goal: make the engine compute the demo scenarios into standard verdict/finding outputs.

Deliverables:

- Checkers/composition updated for the six scenario families.
- Standard severity discipline: red only for hard structural violations, orange for risk indicators, signal/prompt for non-§44 language.
- Explanation strings and provenance for each output.
- Python/unit tests for each scenario.
- Runner output documented.

## Sprint 3 — GUI integration

Goal: connect map, district detail and findings register to the engine outputs only.

Deliverables:

- Map displays streets/schools plus selected demo evidence points/localities from data.
- Detail pages explain each condition and source.
- Findings register filters by scenario type.
- No manual UI-only findings or hardcoded red/orange states.
- Playwright proof screenshots for map, detail and register.

## Sprint 4 — proof, reviewer, PR readiness

Goal: harden the demo and make it reviewable.

Deliverables:

- Full build/test/browser proof.
- Screenshot/GIF evidence in `docs/proof/`.
- PR draft with summary, test plan and visual proof.
- F2 GPT reviewer gate before merge.
