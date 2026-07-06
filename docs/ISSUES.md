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

- `lib/supabase/fetch-all.ts:17` — paging via `.range()` has no deterministic
  `.order()`; a view could in theory return duplicates/gaps across pages. Add
  a stable unique ordering parameter.
- `app/map/page.tsx` / `app/districts/[id]/page.tsx` /
  `app/municipalities/[id]/page.tsx` — `catch → []` silently hides fetch
  errors and renders the map without streets (pre-existing pattern). Log or
  surface an error state.
- `components/region-map.client.tsx:543` — `renderedStreetColors` keyed by
  street name collides when the same street name exists in multiple
  districts (E2E diagnostics only). Key by `district_id + street`.
- `components/region-map.client.tsx:592` — test global
  `window.__soStreetColors` is written in production runtime; gate it to
  test/dev builds.

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
