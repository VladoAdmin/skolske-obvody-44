# Sprint 3, Checkpoint 5 — E2E proof pack (§ 44 demo analysis)

Captured by the real-browser E2E flow (`tests/e2e/proof-pack.e2e.mjs`,
system Chrome via Playwright) against the production build with
`NEXT_PUBLIC_SO_SHOW_COMPLIANCE=1`. Zero JS console errors on every page
visited (map, district detail, findings register).

| Screenshot | What it proves | Checkpoint |
| --- | --- | --- |
| `cp5-map-legend-demo-points.png` | `/map` with the per-district "Nálezy § 44 obvodu" legend (Kritická · DEMO · Š2) after clicking the Kúpeľná district's streets; "Adresné body obvodov" overlay on, framed on the Kúpeľná demo evidence address. Amber demo ring absent — known issue 2 in `docs/ISSUES.md`. | 2 (`57c2d79`) |
| `cp5-district-detail-evidence.png` | District detail (ZŠ Kúpeľná č. 2): scorecard verdicts + "Nálezy a dôkazy § 44" section with the DEMO-tagged Š2 finding and its evidence text. | 3 (`5f3ab57`) |
| `cp5-register-scenario-filter.png` | Findings register with the "Typ scenára" filter set to Prekryv adries (`?scenario=address_overlap`): 2 S2 rows, both DEMO-badged, count line "Zobrazujem 1–2 z 2 nálezov". | 4 (`42b1352`) |

E2E specs: `tests/e2e/proof-pack.e2e.mjs` (full flow above),
`tests/e2e/scenario-filter.e2e.mjs` (register loads, select filters, switching
scenario re-filters, `?scenario=…&page=…` keeps the filter, pagination links
carry the filter when they render). Run instructions in
`tests/e2e/helpers.mjs`.
