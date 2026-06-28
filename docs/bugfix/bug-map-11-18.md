# Bug map — reported issues 11–18

Scope: precise file/line map + root cause for a coding agent. No app code was
changed while producing this. Paths are repo-relative to
`/home/node/.openclaw/workspace/projects/skolske-obvody-44`.

Key architecture facts that recur below:
- The live map is `components/region-map.client.tsx` (1459 lines), wrapped by the
  thin server component `components/region-map.tsx`, embedded by `app/map/page.tsx`
  via `components/map/map-with-panel.tsx`. `components/map/map-client.tsx` is a dead
  MapLibre placeholder (NOT used by `/map`).
- The map uses **Leaflet**, not MapLibre. All layers/controls live in the `mode === 'psk'`
  branch of the second `useEffect` (lines ~418–1436).
- Map data is fetched server-side in `app/map/page.tsx` from Supabase views
  (`so_*`). Views are defined in `db/migrations/*` (read-blocked by a hook — content
  was inspected via grep) and `db/apply_public_schema.sql`.
- Demo data flows through TWO parallel mechanisms (this matters for 12 & 18):
  1. **Engine demo inputs** — `skolske_obvody.district_demo_inputs`
     (`scripts/sql/0036_demo_mode_inputs.sql`), read by `engine/demo_inputs.py`,
     produce the S1/S2/S3/Pa… verdicts + findings shown in the panel.
  2. **Hand-seeded geometry** — `scripts/sql/demo_overlap_island.sql` and
     `scripts/sql/0034_demo_s2_overlap.sql` insert overlap/island polygons into
     `district_overlaps` / `district_islands` that the map draws.
  These two are seeded for DIFFERENT districts and are NOT kept in sync.

---

## 11. App looks too plain — verdict semafor never colours the results rows

**Files/components**
- Global shell: `app/layout.tsx` (header/nav/footer/main), `components/layout/app-header.tsx`,
  `components/layout/app-nav.tsx`, `app/globals.css`, `tailwind.config.ts`.
- Results list (verdicts `V súlade`/`Čiastočne`/`Nesúlad`): the "Zoznam obvodov" table
  in `app/map/page.tsx:326-363`. Verdict→label/symbol mapping is
  `lib/compliance/colors.ts` (`COLOR_LABEL`, `COLOR_SYMBOL`, `COLOR_CLASSES`,
  `getColorClass/getColorLabel/getColorSymbol`).
- Legend that defines the semafor: `components/map/summary-strip.tsx:9-14` (the
  `SEMAFOR` array: RED/ORANGE/GREEN/NONE → emoji + label) plus the inline map legend
  `app/map/page.tsx:306-323`.
- Per-condition coloured cell that DOES work (for contrast): `components/verdict-row.tsx`
  (`ValueBadge` 46-79, semafor cell 172-181, uses `getColorClass`).

**Current behavior**
- `lib/compliance/colors.ts` already exposes `COLOR_CLASSES` (e.g.
  `RED: 'bg-red-100 text-red-800 border-red-300'`). The district-detail scorecard
  (`verdict-row.tsx:175`) applies `getColorClass(...)` to its semafor cell, so colour
  EXISTS there.
- BUT the `/map` "Zoznam obvodov" results table renders only the symbol + label and
  no colour: `app/map/page.tsx:352-356` does
  `getColorSymbol(f.composition_color) + getColorLabel(...)` inside a plain `<span>`
  with no `getColorClass`. Rows have only `hover:bg-muted/30` (line 343). So the
  legend promises a traffic light but the rows are monochrome.
- `tailwind.config.ts` has NO `safelist`. Because the verdict colour classes
  (`bg-red-100`, `bg-green-100`, `bg-orange-100`, etc.) only appear as STRING LITERALS
  inside `lib/compliance/colors.ts`, and `lib/` is NOT in tailwind `content`
  (content = pages/components/app/libs — note `libs/` not `lib/`), these classes can
  be purged unless they happen to appear elsewhere. They currently survive only
  because the same literals appear in `verdict-row.tsx`/`findings-panel.tsx`. This is
  fragile.

**Proposed fix**
- In `app/map/page.tsx:352-356`, wrap the verdict span with
  `getColorClass(f.composition_color)` (add a rounded badge), mirroring
  `verdict-row.tsx:174-180`. Optionally colour the whole `<tr>` left border by verdict.
- Add `lib` to tailwind `content` globs in `tailwind.config.ts:5-10` (currently
  `libs` is listed, `lib` is not) OR add a `safelist` for the
  `bg-(red|orange|green|gray)-100 text-…-800 border-…-300` families so colour classes
  declared in `lib/compliance/colors.ts` are never purged.

**Risk/impact**
- Low. Pure display. Touches `app/map/page.tsx` and `tailwind.config.ts`. The colour
  source of truth (`colors.ts`) already exists; do not fork a second palette.

---

## 12. Clicking finding "ZŠ Kúpeľná… (S2 overlap)" zooms to a purple shade but nothing is highlighted

**Files/components/functions**
- Finding click handler: `components/findings-panel.tsx:59-113` (`handleItemClick`).
  S2 is NOT in `DISTANCE_CODES` (line 57 = `{Pa,Pb,Pc,Pd}`), so the click goes to the
  `else` branch (105-112) → dispatches `EVENT_SELECT_DISTRICT` AND a `EVENT_FLYTO`
  to the **district centroid** at zoom 14 (66-76).
- Map flyTo handler: `region-map.client.tsx:283-287` (centroid fly).
- Select-district handler: `region-map.client.tsx:303-333` — sets the polygon to
  `weight 4.5, fillOpacity 0.55, fillColor hsl(hue,65%,55%)` (the "purple shade" the
  user sees is just the highlighted district fill), `flyToBounds`, then calls
  `drawDemoRef.current(feature)` (322-324) and opens the summary popup.
- Demo illustration builder: `region-map.client.tsx:583-879` (`drawDemoIllustration`).
  The OVERLAP branch is lines 632-663: it filters `overlaps` where
  `is_demo === true && (district_a_id === feature.id || district_b_id === feature.id)`
  and draws the `overlap_geojson` as an amber dashed polygon.
- Overlap data source: `app/map/page.tsx:67-76` fetches `so_district_overlaps`.

**Current behavior / why nothing is drawn**
The overlap polygon for Kúpeľná is effectively absent or invisible at the fly target:
1. **Two competing seeds clobber each other.** `scripts/sql/0034_demo_s2_overlap.sql:18`
   does `DELETE FROM skolske_obvody.district_overlaps WHERE is_demo = TRUE` and then
   inserts ONE Kúpeľná↔Sibírska overlap. `scripts/sql/demo_overlap_island.sql:59-107`
   inserts demo overlaps for **Mirka Nešpora↔Šmeralova** instead. Whichever script ran
   last wins. If `demo_overlap_island.sql` ran after `0034`, there is NO Kúpeľná
   overlap row at all → the filter at `region-map.client.tsx:633-638` matches nothing →
   nothing drawn.
2. **Even when the Kúpeľná row exists it can be empty/tiny.** `0034` derives the strip
   from `ST_LineSubstring(ST_LineMerge(ST_Intersection(ST_Boundary(a),ST_Boundary(b))),
   0.40,0.55)` buffered 25 m (lines 29-67). If the two real polygons only touch at a
   point (not a shared line), the intersection is empty and the `WHERE strip.geom IS
   NOT NULL AND NOT ST_IsEmpty` (66-67) drops the row. When it IS produced it is a ~25 m
   strip ON THE SHARED EDGE, but the panel flies to the district **centroid** at zoom 14
   (`findings-panel.tsx:70-74`), so the strip is off-centre / sub-pixel and reads as
   "nothing highlighted".
3. Closure/timing: `EVENT_SELECT_DISTRICT` is registered in the INIT effect
   (`region-map.client.tsx:303`) and relies on `drawDemoRef.current` being set by the
   MODE effect (`884`). On a cold load that ref is populated, so this is secondary to
   (1)/(2).

**Proposed fix**
- Pick ONE demo overlap seed. Make `0034_demo_s2_overlap.sql` the single source for the
  S2 demo overlap (Kúpeľná↔Sibírska, matching the `0036` engine input that produces the
  Kúpeľná S2 finding), and stop seeding `district_overlaps` from
  `demo_overlap_island.sql` (or align both on the same district pair). Re-run engine →
  re-seed in a fixed, deterministic order.
- In `findings-panel.tsx:59-113`, for S2/overlap findings prefer flying to the OVERLAP
  geometry bounds (or have `drawDemoIllustration` call `map.fitBounds(group.getBounds())`
  in `region-map.client.tsx:854-857` after building the group) so the drawn evidence is
  actually on screen.
- Guarantee the strip is visible: in `0034`, if the boundary intersection is empty, fall
  back to a small buffered polygon around the shared-boundary midpoint so a row always
  exists.

**Risk/impact**
- Medium. Touches seed SQL (`scripts/sql/0034_demo_s2_overlap.sql`,
  `scripts/sql/demo_overlap_island.sql`) + the engine re-run, AND
  `components/findings-panel.tsx` + `components/region-map.client.tsx`. Requires a DB
  re-seed to verify. Coordinate with item 18 (same Šmeralova/overlap seed files).

---

## 13. Missing a "home / reset view" button on the map

**Files/components**
- Map controls live in `components/region-map.client.tsx`:
  - NavigationControl-equivalent: Leaflet default zoom control (implicit on
    `L.map(...)`, lines 226-233).
  - Layer control: `region-map.client.tsx:1381-1392` (PSK) and `496-500` (SK).
  - Existing custom control: the "← Späť na Slovensko" button is a React overlay,
    `region-map.client.tsx:1440-1448` (only shown in `psk` mode).
- The default extent is set by `map.fitBounds(districtsGroup.getBounds(), {padding:[20,20]})`
  at `region-map.client.tsx:1403-1410` (initial) and `1420-1428` (re-add path), with
  `PSK_CENTER`/`PSK_DEFAULT_ZOOM` fallback from `lib/config/region.ts`.

**Current behavior**
- No "home" affordance. After zooming into a finding / district there is no one-click
  way back to the full-obvody extent. The only reset is "← Späť na Slovensko" which
  switches to the SK overview (a different view, not a home of the PSK map).

**Proposed fix**
- Add a Leaflet custom control (house icon) next to the layer control. On click:
  `map.fitBounds(layersRef.current.psk[0].getBounds(), {padding:[20,20]})` (the
  `districtsGroup`), close any popup, call the existing `clearDemoRef.current?.()` to
  drop demo illustrations + selection, and (optional) reset toggled layers to the
  default-ON set (districts + schools). Implement as a React overlay button like the
  existing one at `region-map.client.tsx:1440-1448`, or as `L.Control` registered in the
  PSK branch around line 1383.

**Risk/impact**
- Low–medium. Isolated additive control in `components/region-map.client.tsx`. Reuse the
  existing `clearDemoRef`/`fitBounds` plumbing; do not introduce a second source of the
  default extent.

---

## 14. ROOT CAUSE — "MRK lokality" layer lights up the ENTIRE city of Prešov

**ROOT CAUSE: the data source is whole-municipality, not locality-level.** This is a
**wrong/coarse data source**, not a rendering bug.

**Trace**
- Map layer registration: `region-map.client.tsx:1374`
  `overlays['MRK lokality (Atlas marginalizovaných rómskych komunít)'] = mrkGroup`.
- `mrkGroup` is built at `region-map.client.tsx:1077-1097` from the `mrkOverlays` prop,
  drawing each `mrk.geom_geojson` as a purple hatch polygon.
- `mrkOverlays` is fetched in `app/map/page.tsx:42-51` from view `so_mrk_overlays`.
- `so_mrk_overlays` is defined in `db/migrations/0012_sprint_d_mini_overlays.sql:22-38`:
  `SELECT m.geom … FROM skolske_obvody.mrk_atlas m WHERE ST_Intersects(m.geom, ST_Union(presov districts))`.
- `mrk_atlas.geom` is loaded by `ingest/sprint2_ingest.py:235-290` (`load_mrk_atlas`)
  from WFS layer `wm_ark_municipal` = "Atlas rómskych komunít 2019", keyed by
  **IDN4 / NM4 (obec identifiers)**. The stored polygon is the WHOLE-MUNICIPALITY area
  (`_to_ewkt_multipolygon`, line 268), tagged with a coarse `category`
  (small/medium/large by population) at lines 248-257.
- The engine itself documents this: `engine/c_pe.py:7-13` and `156-157` —
  *"mrk_atlas = obec-level boundaries… For Prešov the whole obec is tagged 'large'.
  This is municipality-level context — it does NOT locate a community within a
  particular district."* The PRECISE localities are in **`mrk_buildings`** (per-building
  point geometries, `ingest/sprint2_ingest.py:293-350`, `load_mrk_buildings`), and the
  engine uses `ST_Within(mrk_buildings, district)` (c_pe.py:104-111), NOT `mrk_atlas`,
  to locate communities.

So the map layer renders the obec polygon → the whole city of Prešov is one big purple
hatch. The Atlas obec polygon is correct context for the engine but wrong for a
"lokality" map layer.

**Fix direction**
- Re-point the map MRK layer to **`mrk_buildings`** (locality-level points) instead of
  `mrk_atlas` (obec polygon). Options:
  1. Add/replace a view (e.g. `so_mrk_localities`) selecting
     `mrk_buildings.geom` (points) for Prešov, and render them as a small dot cluster /
     buffered hull in `region-map.client.tsx:1077-1097`.
  2. Or render a concave/convex hull of the `mrk_buildings` points per locality so the
     hatch shows real locality footprints, not the whole city.
- Keep the obec-level `mrk_atlas` only as the engine's P-e context (already the case);
  do not surface it as a "lokality" map layer.
- Rename the legend if needed (`app/map/page.tsx:311` and the layer label at
  `region-map.client.tsx:1374`) so it reads as locality-level.

**Risk/impact**
- Medium. Needs a new/edited Supabase view + a wired prop in `app/map/page.tsx` + render
  change in `region-map.client.tsx`. Note `mrk_buildings` only covers a handful of MRK
  obce (Varhaňovce, Ostrovany, …) — for Prešov city itself there may be FEW or ZERO
  building points (see `c_s1.py:11` "mrk_buildings only covers MRK villages (not
  Prešov)"). If empty for Prešov, the honest fix is to show nothing / a "no precise
  locality data" note rather than the whole-city polygon. Verify row counts before
  choosing render.

---

## 15. Layers "Domy z VZN" (house points) and "Adresné bodky obvodov" (house dots) are unclear / show nothing

**Files/components**
- Layer registration: `region-map.client.tsx:1376` (`⚙ Expert: Domy z VZN …` →
  `housePointsGroup`) and `1377-1379` (`Adresné bodky obvodov (auto … ≥16)` →
  `houseDotsGroup`).
- `housePointsGroup` build: `region-map.client.tsx:1207-1233` from `housePoints` prop
  (fetched `app/map/page.tsx:166-177` from `so_house_points`). Filters out
  `valid === false` (line 1211); radius 2.5 dots.
- `houseDotsGroup` build: `region-map.client.tsx:1304-1320` from `houseDots` prop
  (fetched `app/map/page.tsx:140-151` from `so_house_dots`). Zoom-gated:
  `HOUSE_DOTS_MIN_ZOOM = 16` (line 21); visibility logic `1322-1350`
  (`updateHouseDotsVisibility`, `overlayadd`/`overlayremove`/`zoomend`).
- There is ALSO a near-duplicate "street geocode" layer `streetPointsGroup`
  (`1185-1200`) that is built but NOT added to the layer control overlays — dead.

**Current behavior — what each binds to**
- **"Domy z VZN"** (`housePointsGroup`): renders valid per-house Google geocodes
  (radius 2.5 px, district-hued). The label claims "460 platných". It is functional but
  visually weak: tiny dots, off by default, and at the default obvody-fit zoom the dots
  are sub-pixel/overlapping → reads as "nothing useful". Not broken, just illegible.
- **"Adresné bodky obvodov"** (`houseDotsGroup`): only appears when the user BOTH toggles
  it on AND zooms to ≥16 (`1330`). At the default extent (whole city) it is invisible by
  design; the label says so, but users select it, see nothing, and don't zoom in.
  Functional but effectively hidden. If `so_house_dots` returns 0 rows the toggle is not
  even registered (`1377` guards on `houseDots.length > 0`).

**Decision per layer**
- "Domy z VZN": KEEP but improve, OR fold into "Adresné bodky". It is real evidence
  (Google-geocoded VZN house ranges). If kept, increase radius / add zoom gating like
  houseDots so it is legible. It overlaps conceptually with houseDots (both are per-house
  dots) — consider merging the two into ONE "Adresné body" layer to remove confusion.
- "Adresné bodky obvodov": KEEP (it is the cleaner per-house layer) but make discovery
  obvious — e.g. auto-zoom on toggle, or show a tooltip "priblížte sa pre zobrazenie".
- Remove the dead `streetPointsGroup` build (`1185-1200`) if it is never exposed.

**Risk/impact**
- Low–medium. Display-only in `region-map.client.tsx`. Verify `so_house_points` /
  `so_house_dots` row counts first (if both ~empty, simplest fix is to drop the toggles).
  Touches the same file as 12/13/14/16 — sequence carefully.

---

## 16. Layer legend/control should be collapsible (slide-away)

**Files/components**
- Leaflet layer control: `region-map.client.tsx:1381-1392` (PSK overlays) and
  `496-500` (SK). The `collapsed` option is driven by
  `layerControlCollapsed()` (`region-map.client.tsx:142-145`) which returns `true` only
  on `max-width:767px` (mobile) — so on DESKTOP the control is permanently EXPANDED and
  blocks the top-right of the map.
- Mobile CSS that already collapses it into a "Vrstvy" pill: `app/globals.css:71-93`.
- Demo-finding legend box (separate DOM legend, bottom-left): created in
  `region-map.client.tsx:862-878` (`demo-finding-legend`), with
  `pointer-events:none` (865) so it cannot be collapsed/dismissed.
- Static legend below the map: `app/map/page.tsx:306-323`.

**Current behavior**
- Desktop: layer control is always open (expanded checkbox list), covering map content
  top-right. There is no collapse toggle on desktop.

**Proposed fix**
- Make the Leaflet layer control collapse on desktop too: either pass `collapsed: true`
  unconditionally at `region-map.client.tsx:1382` (Leaflet then shows the hamburger icon
  and expands on hover/click), or add a custom collapse toggle. The mobile pill styling
  in `globals.css:71-93` can be promoted to all widths.
- Optionally make the bottom-left `demo-finding-legend` (862-878) dismissible.

**Risk/impact**
- Low. One-line option change plus optional CSS. Isolated to
  `region-map.client.tsx:1382` (+ `app/globals.css`). Beware: `layerControlCollapsed()`
  is also used for the SK control at line 499 — change both or change the helper.

---

## 17. DEMO notices scattered everywhere — keep ONE top banner (+ optional first-load popup)

**Every occurrence (file:line)**

Reusable banner component (the one to KEEP):
- `components/disclaimer-banner.tsx` (server wrapper) + `components/disclaimer-banner.client.tsx`
  (the actual amber Alert, title "Demo — nie oficiálny výklad", lines 44-72;
  session-dismiss via `localStorage` key `dismiss_disclaimer_session`).

Places that render `<DisclaimerBanner>`:
- `app/page.tsx:3,30` (`<DisclaimerBanner />`, dismissible)
- `app/findings/page.tsx:2,66` (`<DisclaimerBanner />`)
- `app/districts/[id]/page.tsx:4,171` (`<DisclaimerBanner alwaysShow />` — non-dismissible)
- `app/o-metodike/page.tsx:3,34` (`<DisclaimerBanner alwaysShow />`)

Scattered inline disclaimers / DEMO text NOT using the banner:
- `app/map/page.tsx:232-256` — its own collapsible amber `<details>` "Demo dáta —
  Register adries MŠSR nedostupný" (separate from `<DisclaimerBanner>`; `/map` does NOT
  use the shared banner).
- `app/map/page.tsx:258-276` — blue "Ako čítať mapu" `<details>` (informational, not a
  disclaimer; can stay or fold in).
- `components/findings-panel.tsx:187-194` — per-finding red `DEMO` badge (line 192).
- `components/findings-table.tsx:31` and `:197` — `DEMO` badge + "Ukážkové (DEMO) dáta…"
  caption.
- `components/verdict-row.tsx:192-199` — per-row `DEMO` badge with tooltip (line 195).
- `app/districts/[id]/page.tsx:321-326` — per-island `DEMO` badge (line 323).
- `components/region-map.client.tsx` — in-map demo tooltips/labels and the
  `demo-finding-legend` box: lines 617, 634-661 (overlap "demo"), 791 (P-e label),
  833-834/841 (P-f "preplnené … demo"), 862-878 (legend box header "Nálezy § 44 (demo)").
- `app/o-metodike/page.tsx:115,177,602` — "Ilustratívny… nezáväzný", "len signál, nie
  záväzný verdikt", "nie záväzný" prose (methodology page; intended, can stay).

**Distinction for the fix**
- TRUE page-level disclaimers (remove the scattered ones, keep ONE top banner + optional
  first-load popup): `app/map/page.tsx:232-256` (the `/map` inline `<details>`) and the
  duplicated `<DisclaimerBanner>` usages across pages. Recommend: render ONE
  `<DisclaimerBanner>` once (e.g. in `app/layout.tsx` or a top slot) with a
  first-load-popup variant, and delete the per-page copies + the `/map` inline `<details>`.
- KEEP the per-row/per-finding/in-map `DEMO` badges — those are honest data-provenance
  flags (`is_mock` / `is_demo`), NOT a scattered disclaimer; removing them would hide
  which values are mock (a project invariant). Item 17 is about the repeated full-width
  prose banners, not these inline badges. Confirm scope with the requester before
  stripping badges.

**Risk/impact**
- Low–medium. Mostly deletions across `app/page.tsx`, `app/findings/page.tsx`,
  `app/districts/[id]/page.tsx`, `app/o-metodike/page.tsx`, `app/map/page.tsx`, plus one
  add in `app/layout.tsx`. Do NOT remove the `is_mock`/`is_demo` provenance badges
  (project rule: mock data must stay visibly flagged).

---

## 18. ROOT CAUSE — Šmeralova finding says obvod has >1 school, but only ONE (private) school renders

**ROOT CAUSE: the "two public schools" claim is a fabricated DEMO INPUT NUMBER with no
corresponding second school feature on the map. It is a demo-data/render mismatch, not
bad geometry.**

**Trace**
- The Šmeralova RED finding is **S3** ("jedna škola na obvod"), not S1. Demo seed:
  `scripts/sql/0036_demo_mode_inputs.sql:91-93`:
  `('Základná škola, Šmeralova č. 25', … s3_school_count = 2 …,
   'DEMO RED: dve verejné školy v jednom obvode (S3 FAIL).')`.
- Engine S3 demo path: `engine/c_s3.py:39-69` (`_check_s3_demo`) reads
  `demo['s3_school_count']` and emits FAIL when `count != 1` with text
  "{count} verejné školy typu ZS v jednom obvode" (lines 53-57). This number (2) is a
  pure scalar from the demo input row — the engine does NOT place or require a second
  school geometry.
- The map renders schools from real data only:
  - per-district VZN school: `region-map.client.tsx:1028-1051` (one marker per
    `feature.school_geom_geojson`).
  - other schools: `region-map.client.tsx:1053-1072` from the `schools` prop
    (`so_school_markers`, `app/map/page.tsx:31-40`), coloured public=blue / private=amber
    via `is_public` (`1059-1060`).
- So for the Šmeralova obvod the map shows whatever real schools physically sit there.
  The user sees ONE marker and it is amber (private). There is no second PUBLIC school in
  the data for that area, but the demo finding asserts two. Hence the discrepancy: the
  finding's `s3_school_count=2` is decoupled from the rendered schools.
- Note: the real (non-demo) S3 checker (`c_s3.py:98-174`) counts only
  `is_public = TRUE` schools via `ST_Within(school.geom, district.geom)`. Private/church
  schools are explicitly excluded (`c_s3.py:9-14, 104`). So even a real run would not
  count the amber private school. The demo just hard-codes "2" without seeding the second
  public school point.

**Concrete cause**
Demo input `s3_school_count = 2` (a scalar) with NO second public-school marker seeded →
finding text says "two public schools" while the map can only render the real ONE
(private) school in that area. The "only one, and it's private" is exactly what the
underlying `schools`/`features` data contains.

**Fix direction (pick one)**
1. **Make the demo honest on the map:** seed a second DEMO public-school point inside the
   Šmeralova obvod (a `schools` row with `is_public=TRUE`, `is_demo=TRUE`) so the map
   actually shows two public schools matching the S3 FAIL. Render it via the existing
   schools loop with a DEMO badge. (Mirrors how `0034` seeds demo overlap geometry for
   S2.) — Best for a convincing demo.
2. **Make the finding match reality:** change the Šmeralova demo so the S3 evidence text
   references the actual rendered school(s), or move the S3 demo to a district that truly
   has two public schools in its geometry. — Simpler, less illustrative.
3. At minimum, in the finding/popup explain that the second school is illustrative
   (DEMO) so the map↔finding mismatch is not read as a bug.

Also verify the Šmeralova `feature.school_name`/`is_public`: if the VZN-assigned school
for that obvod is itself private, the per-district pin (`1028-1051`) draws it without the
public/private colour split (it always uses `SCHOOL_COLOR_PUBLIC` blue at line 1035) —
worth confirming so the "it's private" observation is consistent.

**Risk/impact**
- Medium. Option 1 touches a schools seed SQL + a re-seed; option 2 touches
  `scripts/sql/0036_demo_mode_inputs.sql` + engine re-run. No app logic change strictly
  required, but the schools render path (`region-map.client.tsx:1028-1072`) should be
  reviewed. Shares seed/engine-rerun surface with item 12.

---

## Shared files / conflict risk (sequence carefully)

| File | Items | Note |
|------|-------|------|
| `components/region-map.client.tsx` | 11(read), 12, 13, 14, 15, 16, 17(in-map labels) | **Highest contention.** 12 (drawDemoIllustration ~583-879 + fitBounds), 13 (new control ~1383/1440), 14 (mrkGroup 1077-1097), 15 (house layers 1207-1350 + control 1376-1379), 16 (layer-control `collapsed` 1382 + helper 142-145), 17 (demo legend 862-878). Do 14/15 (layer data+render) first, then 16 (control option), then 12 (illustration/fit), then 13 (new control). |
| `app/map/page.tsx` | 11, 14, 15, 17 | 11 (results table colour 352-356), 14 (legend text 311 + possible new mrk prop), 15 (house fetches 140-177), 17 (remove inline `<details>` 232-256). |
| `scripts/sql/0034_demo_s2_overlap.sql` | 12 | Single S2-overlap seed; conflicts with `demo_overlap_island.sql`. |
| `scripts/sql/demo_overlap_island.sql` | 12, 18 | Seeds Nešpora/Šmeralova overlap+island; overlaps with 0034 (12) and the Šmeralova demo (18). Pick one overlap seed. |
| `scripts/sql/0036_demo_mode_inputs.sql` | 12, 18 | Drives Kúpeľná S2 (12) and Šmeralova S3=2 (18) findings. Engine re-run required after edits. |
| `tailwind.config.ts` | 11 | content/safelist for verdict colour classes. |
| `app/globals.css` | 16 | layer-control collapse CSS (currently mobile-only 71-93). |
| `lib/compliance/colors.ts` | 11 | source of truth for verdict colour/label/symbol — reuse, do not fork. |
| `components/disclaimer-banner*.tsx`, `app/page.tsx`, `app/findings/page.tsx`, `app/districts/[id]/page.tsx`, `app/o-metodike/page.tsx`, `app/layout.tsx` | 17 | consolidate the page-level banner into one. |
| Engine re-run (`python3 -m engine.runner`) | 12, 18 | Any change to `district_demo_inputs` requires a clean engine re-run (engine_version = git hash); demo findings/verdicts are regenerated, not hand-edited. |

**Suggested order:** 11 → 16 → 14 → 15 → 13 (display/control, low risk, mostly
independent) → then the data-coupled pair 12 + 18 together (shared seed files + one
engine re-run) → 17 last (touches many pages but mostly deletions).
