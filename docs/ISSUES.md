# Known issues

Bugs found during real-browser E2E (Sprint 3, Checkpoint 5). Both fixed in
Sprint 4; kept for the record.

## 1. [FIXED] "Adresné body obvodov" overlay never shows dots when toggled from zoom < 16

**Fixed in `db89707`** (Sprint 4): programmatic add/removeLayer in
`updateHousePointsVisibility` is guarded by a `syncingHousePoints` flag, so
the re-fired `overlayremove` can no longer reset `housePointsEnabled` — only
user toggles flip it. Regression spec: `tests/e2e/overlay-toggle.e2e.mjs`.

- **Page:** `/map`
- **Action:** at the initial city zoom (12), enable the layers-control overlay
  "Adresné body obvodov (441, priblížte ≥ 16)".
- **Expected:** the documented auto-zoom kicks in (`overlayadd` →
  `map.setZoom(16)`) and the address dots render.
- **Actual:** the map zooms to 16 but no dots ever appear. The `overlayadd`
  handler calls `updateHousePointsVisibility()` synchronously while the zoom is
  still 12, which calls `map.removeLayer(housePointsGroup)`; that fires
  `overlayremove`, whose handler resets `housePointsEnabled = false`, so the
  `zoomend` re-check keeps the layer off. The layers-control checkbox stays
  visually checked. (`components/region-map.client.tsx:707-731`)
- **Console errors:** none.
- **Workaround:** zoom to ≥ 16 first, then toggle the overlay — dots render
  (441 paths). The E2E proof pack uses this order
  (`tests/e2e/proof-pack.e2e.mjs`).

## 2. [FIXED] Amber demo ring never renders on `/map` address dots

**Fixed in `4f97af2`** (Sprint 4): `fetchHousePoints()` selects `is_demo`;
the proof-pack spec now hard-asserts the amber ring, and
`tests/e2e/overlay-toggle.e2e.mjs` asserts it marks only the demo subset.

- **Page:** `/map`, "Adresné body obvodov" overlay at zoom ≥ 16 framed on a
  demo evidence address (e.g. Kúpeľná S2 seed, 48.973544, 21.221561).
- **Expected (Checkpoint 2):** demo evidence points render with the amber
  dashed ring (`#b45309`) so seeded §44 scenario addresses read as
  illustration.
- **Actual:** 0 amber rings. `fetchHousePoints()` (`app/map/page.tsx:141`)
  omits `is_demo` from its select, so `hp.is_demo` is always `undefined` and
  the amber branch (`components/region-map.client.tsx:680`) never triggers.
  The view itself exposes `is_demo` (verified via REST) — the fix is adding
  the column to the select.
- **Console errors:** none.

## 3. [BACKLOG] Sprint 5 GPT-5.5 review findings (non-blocking hardening)

Deferred to backlog per owner's standing decision (same as the two Sprint 3/4
review findings). None blocks the pagination fix — the E2E gate proves 2974
segments fetched and rendered.

- ~~`lib/supabase/fetch-all.ts:17` — paging via `.range()` has no deterministic
  `.order()`~~ **[FIXED VLA-10]** `fetchAllRows` now takes a required
  `orderBy` param; `so_district_street_linestrings` gained a genuinely
  unique `segment_id` column (`scripts/sql/0046_street_segment_id.sql`) since
  `(district_id, school_id, street, is_fallback_point)` isn't unique — 2863
  of 2974 rows share it with a sibling segment.
- `app/map/page.tsx` / `app/districts/[id]/page.tsx` /
  `app/municipalities/[id]/page.tsx` — `catch → []` silently hides fetch
  errors and renders the map without streets (pre-existing pattern). Log or
  surface an error state.
- `components/region-map.client.tsx:543` — `renderedStreetColors` keyed by
  street name collides when the same street name exists in multiple
  districts (E2E diagnostics only). Key by `district_id + street`.
- ~~`components/region-map.client.tsx:592` — test global
  `window.__soStreetColors` is written in production runtime; gate it to
  test/dev builds.~~ **[FIXED VLA-13, `430fe5a`]** The write is now gated
  behind `NEXT_PUBLIC_SO_E2E_HOOKS === '1'` (unset in Vercel prod, `1` in
  `.env.local` for local dev/E2E builds — same pattern as
  `NEXT_PUBLIC_SO_SHOW_COMPLIANCE`). NODE_ENV couldn't gate this: it's
  `production` in both the real deploy and the local E2E production build.
  Verified undefined in a no-flag production build (real headless Chrome);
  both E2E consumers (`street-coverage.e2e.mjs`,
  `vla21-shared-municipality-areas.e2e.mjs`) still pass with the flag on.

## 4. [BACKLOG] VLA-14 review findings (gpt-5.4 fallback, 2026-07-06; blockers verified false)

Both BLOCKERs disproven against real code (ast.parse OK, tsc --noEmit clean,
imports valid — diff-reading artifacts). Deferred per owner's standing decision:

- `components/region-map.client.tsx` — `else dataGapCount++` counts any
  non-vzn_gap as data_gap; tighten to explicit `=== 'data_gap'`.
- `components/region-map.client.tsx` — `gapCategories[gap.street]` keyed by
  display name; collides on duplicate street names, key by street_norm.
- `so_street_coverage_gaps` view + fetch lack a `municipality_id` filter —
  fine for Prešov-only demo, required before a second municipality.
- coverageGapsGroup added to map unconditionally while overlay control is
  conditional on non-empty — unify.
- summary counts rows, not unique streets — guarantee 1 row/street in view
  contract or count street_norm.

## 5. [BACKLOG] VLA-19 legal-audit follow-ups (out of evidence-text scope)

Found during the § 44 legal audit (`docs/legal-audit-44.md`, 2026-07-06).
Neither is user-visible today; both must be fixed before the affected surface
ships.

- **`skolske_obvody.finding_explanations` (AI explanations, DB):** rows contain
  invented legal claims — e.g. Pa FAIL "Podľa § 44 nemá byť škola vzdialená
  viac než 2 km", Pc/Pd FAIL framed as "porušenie podľa § 44". The table is
  currently dormant (no UI component reads `so_finding_explanations`; only the
  type in `lib/supabase/types.ts` remains). Before any UI re-enables it,
  regenerate all rows from the corrected labels/evidence texts and add the
  citation gate (`tests/test_legal_citations.py`) to the generation path —
  or drop the table.
- **`app/o-metodike/page.tsx` — section "Ako vyhodnocujeme § 44 zákona 321":**
  the criteria table describes a stale taxonomy (Š4, Pa = kapacita,
  Š3 = segregácia, Pb thresholds as norms) that matches neither the engine
  (`engine/c_*.py`) nor § 44. VLA-19 fixed the law number and the condition
  cards above it; the table itself needs a rewrite against
  `docs/legal-audit-44.md`. The hardcoded engine-version footer on the same
  page is also stale.

## 6. [PRE-EXISTING, NOT CAUSED BY VLA-10] `proof-pack.e2e.mjs` fails to find a clickable point on a highlighted Kúpeľná street

`tests/e2e/proof-pack.e2e.mjs` samples 5 points along each `stroke-width=5`
(highlighted) SVG path and asserts `document.elementFromPoint` returns that
same path at at least one point. This currently fails.

**Verified NOT a VLA-10 regression**, by three separate baselines: (1) with
VLA-10's `.order('segment_id')` applied, (2) with `.order()` disabled but the
`segment_id`-bearing view still live, (3) fully reverted to unmodified `main`
— original `so_district_street_linestrings` view, no `.order()`, original
select lists. All three fail identically and deterministically (3 runs each).
The other 6 E2E specs (`street-coverage`, `coverage-gaps`, `overlay-toggle`,
`scenario-filter`, `vla15-evidence-trail`, `vla20-ui-cleanup`) are green on
VLA-10's branch, including the 2974-segment count this job's acceptance
criterion depends on.

Root cause not yet isolated (candidate: an overlapping non-highlighted street
path or a UI layer occluding all 5 sampled sample points on the highlighted
path — needs a dedicated investigation, out of scope for VLA-10). Deferred to
backlog; not blocking this job's acceptance criteria, which are scoped to the
street-count regression signal and the other 6 specs.

## #7 — VLA-16 mobile-responsive follow-up: GPT-5.5 non-blocking hardening items (2026-07-10)

From GPT-5.5 review of e110679/ab81a31/0a810ba/d2078c1 (PR #3), logged as
follow-up, not blocking merge (reported 375px/768px bugs are fixed and
tested):
- Bottom-right zoom control untested vs attribution control + MRK exclusion
  popups; no safe-area-inset handling for iOS home-indicator area.
- `sm:` (640px) breakpoint untested in 640-767px range; is viewport- not
  container-based, could reintroduce overlap in a narrower parent.
- mobile-responsive.e2e.mjs: only checks outer bounding boxes (not text
  overflow), only checks zoom-vs-back-button (not attribution/popups), no
  explicit wait for fonts/hydration before assertions, 4px y-tolerance at
  768px could mask a partial wrap, `deviceScaleFactor: 1.4` is nonstandard
  vs real-device DPR 2/3.
- Re-adding `L.control.zoom()` post-construction may change keyboard tab
  order vs the back button — worth a manual check.

## #8 — [PRE-EXISTING, NOT CAUSED BY VLA-18] `districts.geom` polygon coverage hole at Sekčov (2.70 km²)

Found during VLA-18's investigation of whether a real street/district data
gap remains to mock-fill (`log/2026-07-11-vla-18-datagap-mock.md` §2).
`ingest.build_street_districts.check_coverage()` reports 96.0% polygon
coverage of the municipality boundary (67.55 / 70.39 km²), 2.836 km² of
holes across 30 disjoint pieces. One hole dominates: **270.36 ha (2.70 km²)**
centered on the Sekčov housing estate (48.99491, 21.29922); the other 29 are
slivers under 6 ha each.

**Root cause:** `ingest/build_street_districts.py`'s `ASSIGN_SQL` uses
`INNER JOIN ... ON ST_Contains(cell_geom, seed.geom)` to assign Voronoi
cells to district seeds — an `INNER JOIN` silently drops any Voronoi cell
that doesn't strictly contain a seed point. At Sekčov's seed density (many
streets, many house points, tight spacing) this drops real cells from the
polygon union. Confirmed NOT a data problem: `check_overlaps()` returns 0
double-claimed pairs, `house_geocodes` inside the hole = 0 (no
under-geocoded cluster), and every street touching the hole (Bajkalská,
Sekčovská, Terchovská, Levočská, Duklianska, Prostějovská, Antona
Prídavka, K Surdoku, Ku Kráľovej hore, Jána Hollého, Jilemnického,
Raymanova, Teriakovská) has a real row in
`skolske_obvody.vzn_street_ranges` assigning it to a real district. This is
a Voronoi-tessellation join artifact in the polygon builder, unrelated to
VLA-14/18/20's street-coverage work.

**Not user-visible today:** `districts.geom` / `geom_geojson` is fetched by
`so_district_map_features` but not rendered by any map component — the
streets-pivot sprint (VLA-16) switched rendering to street linestrings only
(`app/map/page.tsx:82-84`; confirmed by grep of `region-map.client.tsx` and
`district-detail-map.client.tsx`, neither references `geom_geojson`).

**Not fixed here** — this is a geometry-algorithm bug in
`ingest/build_street_districts.py` (change the join to preserve
seedless-but-covered cells, or fall back to nearest-seed assignment),
categorically different work from VLA-18's mock-assignment scope, and has
zero current user impact since the polygon layer is dead in the UI.

## #9 — [PRE-EXISTING, NOT CAUSED BY VLA-18] `rest-smoke.test.ts` scorecard test asserts a stale `condition_order` upper bound

`tests/integration/rest-smoke.test.ts` — "should expose so_district_scorecard
with condition_order 1-9" asserts `condition_order <= 9`; the live
`so_district_scorecard` view returns `condition_order = 10` for the `JAZYK`
(language) condition. Confirmed pre-existing on the VLA-18 branch base
(`git show 1163ecd:tests/integration/rest-smoke.test.ts` already has the
`1-9` hardcoded bound, before any VLA-18 commit touched this file), and the
view's `CASE WHEN 'JAZYK' THEN 10` has existed since `scripts/sql/
0033_jazyk_label_views.sql` (commit `397919c`) — the smoke test's upper
bound has been stale since then, unrelated to any recent VLA ticket. Not
fixed here: out of VLA-18's scope and the test assertion, not the
underlying data, is what's wrong. Needs the upper bound updated to the
live condition count (data-driven, not re-hardcoded) in a follow-up.
