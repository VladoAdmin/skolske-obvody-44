# CC Brief — Školské obvody §44: STREETS pivot (step 1)

Owner: F2 orchestrator. This is the **fixed mandate** from Vlado (voice, 2026-06-28 ~18:47).
Read `handoffs/SKOLSKE_OBVODY_44_SESSION_HANDOFF_2026-06-28-evening.md` for current state first.

## Why (root complaint)
We keep changing ONE thing (the polygons) without thinking through every downstream
dependency, so findings/detail-page/overlaps end up inconsistent with the map. This task
MUST handle every dependency in one coherent pass. Do not fake the display or the
calculations — edit the DATA so honest rendering is clean.

## THE PIVOT (step 1 only — analysis/mock is a SEPARATE step 2, do NOT build it now)

1. **Remove ALL district polygons** from the UI — both the **main map** and the **per-school
   detail page**. No polygon fills, no Voronoi shapes, no island outlines, no overlap polygons.
   Delete the polygon render paths, don't just hide them.

2. **Render each district as its STREETS, colored per school.** Each district/school gets a
   distinct stable color. A district = the set of VZN streets that belong to its school, drawn
   as colored linestrings.
   - Data is available: `skolske_obvody.osm_street_lines.geom` (LineString 4326) joined to
     `skolske_obvody.street_geocodes(district_id, street)` by normalized street name.
   - Create a public view `so_district_street_linestrings(district_id, street, linestring_geojson)`
     (ST_AsGeoJSON). For the ~5% VZN streets with no OSM line, fall back to the
     `street_geocodes` point rendered as a small dot in the school color (so no street is missing).
   - Click a school/district → its streets highlight (full weight/opacity), others dim.
     Default (nothing selected) = every district shown in its own color.

3. **Shared streets are NOT a finding.** A street can belong to 2+ districts (crossing/boundary)
   — that is fine. When a street is in multiple districts, draw it in each district's color; on
   click show it in the clicked district's color. Never flag a shared street as a violation.

4. **What matters is ADDRESS points (street + house number).** The only structural overlap that
   could ever be a finding is the **same full address (ulica + popisné/orientačné číslo) assigned
   to 2+ districts**. Re-anchor any structural overlap logic to address points, not polygon
   intersection. (Current Š2 uses `ST_Intersects(d1.geom, d2.geom)` — that polygon-based overlap
   is now meaningless and must go.)

5. **WIPE ALL current findings (nálezy).** Step 1 ships a clean street map with **zero findings
   shown** — no Pa distance, no Pc transfers, no S2 overlap, no island findings, nothing. The
   findings panel is empty/removed for now. Vlado reviews the clean street look first; the mock
   analysis layer is rebuilt in step 2.

6. **Detail page parity (critical — past failure):** the per-school detail page currently still
   draws the old jagged Voronoi polygons. It MUST use the exact same street rendering as the main
   map: selected school's streets in its color, neighbor context faint. No polygon anywhere.

## Do NOT touch / out of scope for step 1
- Do not invent or rely on legal thresholds (e.g. "30 min walk", ">2 MHD transfers"). Those are
  questioned by Vlado and belong to step 2 where we verify against actual §44 text. Since all
  findings are wiped in step 1, this resolves itself — just don't surface them.
- Do not build the mock segregation/minority/distance analysis. That is step 2.
- Keep schools as pins. Keep address points renderable.

## Honesty / data-driven invariant (keep)
- Engine = SSOT. Any data shaping happens via ingest scripts → DB, never hardcoded verdicts in UI.
- If you shape geometry/assignment, verify address containment with a real DB query.

## Acceptance criteria (verify for real, with evidence)
- [ ] Main map: 12 districts each render as colored street networks; NO polygons anywhere.
- [ ] Click a school → its streets highlight in its color, others dim; click another → switches.
- [ ] Shared streets render and are NEVER flagged as findings.
- [ ] Detail page renders identical street style (no jagged polygons).
- [ ] Findings panel shows ZERO findings (all wiped).
- [ ] Address points: same full address in 2+ districts is the ONLY structural-overlap concept
      left in code (even if it surfaces nothing now — the logic is address-based, not polygon).
- [ ] DB check: every street linestring drawn belongs to a real VZN street→district mapping
      (no fabricated geometry). Report streets-without-OSM-line count (rendered as dots).
- [ ] Real browser proof: Playwright/Chrome (`/usr/bin/google-chrome-stable`) screenshot of main
      map + detail page, 0 console errors. Save under docs/proof/streets-*.png.
- [ ] `python3 -m engine.runner` still runs clean (no RED-only-structural error); since findings
      are wiped, document what the runner now emits.

## Process
- Branch `feat/streets-pivot`. Commit convention as repo. Co-Authored-By: Františka 2.
- When green + proof captured, STOP and report back to F2 for GPT-5.5 reviewer gate before merge.
- No merge to main without reviewer APPROVE + browser proof.
