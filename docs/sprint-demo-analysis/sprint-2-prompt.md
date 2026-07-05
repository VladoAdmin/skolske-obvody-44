TASK: Skolske obvody §44 Step 2, Sprint 2 — engine verdicts and findings for the six demo scenario families

PROJECT PATH:
/home/node/.openclaw/workspace/projects/skolske-obvody-44

ROLE:
You are Claude Code implementing a bounded coding sprint in the project repo. Work only inside the project path. Do not deploy, do not merge, do not touch credentials, and do not read F2 workspace files outside this project. Be terse in outputs; no narration.

CURRENT VERIFIED STATE FROM F2:
- Branch: `feat/streets-pivot`, HEAD `f169333` (Sprint 1: demo input contract + S2 address-overlap foundation), pushed to origin.
- Sprint 1 passed external CODE review (GPT-5.5): APPROVE WITH CHANGES.
- Sprint plan: `docs/sprint-demo-analysis/SPRINTS.md` (Sprint 2 section is your scope). Sprint 1 inventory: `docs/sprint-demo-analysis/S1_NOTES.md`.

FIRST ACTION — LINEAR ISSUE (mandatory):
Use the Linear MCP (`/mcp` linear) to create an issue titled "SO44 Step2 Sprint2 — engine verdicts for 6 demo scenarios" with a short description and move it to In Progress. Update it at milestones and move to Done with a summary comment when the sprint completes. If Linear MCP errors, record the error in `docs/sprint-demo-analysis/S2_NOTES.md` and CONTINUE the sprint — Linear must never stall coding.

REQUIRED FIXES FROM SPRINT 1 REVIEW (do these first):
1. `scripts/sql/0041_demo_s2_address_overlap.sql`: add pre-INSERT validation that the two target districts exist and both have school_type='ZS' and teaching_language='SK'; fail loudly (RAISE) instead of silently inserting non-matching demo data.
2. `engine/demo_inputs.py`: `@lru_cache(maxsize=1)` on `_demo_mode_enabled()` makes a mid-process demo-mode toggle invisible. Runner is one-shot today — add an explicit `refresh_demo_mode()`/cache-clear hook called at runner start, and document the one-shot assumption where the cache is defined.
3. Document (comment) the pre-existing f-string SQL interpolation of school_type/teaching_language in `engine/c_s2.py` as internal-trusted-only; do not refactor it in this sprint.

SPRINT 2 SCOPE (per SPRINTS.md):
- Apply migration 0041 (after fix above), enable demo mode, run `python3 -m engine.runner`, verify the S2 address-overlap demo produces FAIL with is_mock provenance and that the RedOnlyStructuralError guard behaves correctly.
- Update checkers/composition so ALL six scenario families compute into standard verdict/finding outputs: MRK/segregation risk, capacity pressure, long distance, difficult route, language minority (outside §44), same-full-address overlap.
- Severity discipline: RED only for hard structural violations (S1/S2/S3); risk indicators max ORANGE; language = signal/prompt outside the semaphore, never red.
- Explanation strings + provenance (is_demo/is_mock) for each output; texts anchored to labels.ts naming.
- Python/unit tests per scenario family — each test must FAIL if the demo/live gate leaked or severity discipline broke.
- Document runner output in `docs/sprint-demo-analysis/S2_NOTES.md`.

HARD INVARIANTS (violations = do not commit):
- Engine is the sole source of truth; GUI renders engine output only.
- Demo/mock enters ONLY via provenance-tagged INPUT tables; NEVER influences live/prod verdicts with demo mode off.
- Real VZN/address/street/geocode data stays unchanged.
- Shared street alone is never a finding; only same FULL address in multiple districts.
- No deploy, no merge, no credentials.

OUT OF SCOPE: map/register UI (that is Sprint 3), new legal thresholds.

TEST GATE BEFORE COMMIT:
- `python3 -m pytest tests/ -q` green (no skips without explicit reason).
- `npm run build` and `npm run lint` green if TS files were touched.
- Max 3 fix attempts per failing test, then record in docs/ISSUES.md and note in commit message.

COMPLETION PROTOCOL:
1. Single milestone commit on `feat/streets-pivot`: `feat(demo-analysis): step-2 sprint-2 engine verdicts for six demo scenarios` (+ detail bullets; mention any deferred items). Commit signature per repo convention.
2. After committing, write a completion line to `/home/node/.openclaw/workspace/projects/skolske-obvody-44/.cc-inbox/skolske-step2-sprint2.done` containing: exit=0, commit sha, tests summary, one-line result. Create the directory if missing.
3. Close the Linear issue with a summary comment.
