# Known issues

Bugs found during real-browser E2E (Sprint 3, Checkpoint 5). App fixes are
out of scope for the proof sprint — each needs its own fix sprint.

## 1. "Adresné body obvodov" overlay never shows dots when toggled from zoom < 16

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

## 2. Amber demo ring never renders on `/map` address dots

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
