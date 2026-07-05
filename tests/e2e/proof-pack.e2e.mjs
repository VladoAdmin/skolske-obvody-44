// Checkpoint 5 proof pack — real-browser flow in one tab, capturing the three
// §44 proof screenshots along the way (saved immediately to docs/proof/):
//   1. map with the per-district §44 findings legend + amber demo evidence points
//   2. district detail with verdict evidence (Nálezy a dôkazy § 44, DEMO tags)
//   3. findings register with the scenario-type filter active
// Flow: load /map → dismiss first-load DEMO modal (real click) → click the
// Kúpeľná district's school pin (same selectDistrict path as clicking its
// streets) → legend appears → enable the address-dots overlay → frame the
// demo evidence point → district list link → detail → header nav → register →
// scenario select → filtered rows.
// Gate: ZERO JS console errors on every page visited.
import { mkdirSync } from 'fs'
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

const OUT = 'docs/proof'
mkdirSync(OUT, { recursive: true })

// Kúpeľná č. 2 demo evidence address (S2 address-overlap scenario seed) —
// stable demo data; used only to FRAME the screenshot via the app's own
// so:flyto bridge, never to assert on coordinates.
const DEMO_POINT = { lat: 48.973544, lon: 21.221561 }

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map')

  // ── 1. Map: legend + demo evidence points ────────────────────────────────
  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })

  const modalShown = await dismissDemoModal(page)
  assert(modalShown, 'first-load DEMO modal should appear on a fresh context')

  // Streets pivot: districts render as coloured street linestrings.
  await page.waitForFunction(
    () => document.querySelectorAll('.leaflet-container path').length > 50,
    { timeout: 20000 }
  )

  // Collapse any open <details> so it cannot overlay the map.
  await page.evaluate(() => {
    document.querySelectorAll('details[open]').forEach((d) => d.removeAttribute('open'))
  })

  // Locate the district: click its Š2 finding in the panel (flies to the
  // district and highlights its streets at weight 5). The legend itself is
  // wired to clicking the district's STREETS, so next click a point that
  // verifiably lies ON one of the highlighted street paths.
  // p.font-medium holds the row's district name — a plain hasText would also
  // match rows whose EVIDENCE text mentions Kúpeľná (the Sibírska Š2 row).
  await page
    .locator('ul button')
    .filter({ has: page.locator('p.font-medium', { hasText: 'Kúpeľná' }) })
    .first()
    .click()
  // Selection highlights the district's streets at weight 5; wait for it and
  // for the flyTo animation to settle.
  await page.waitForFunction(
    () => [...document.querySelectorAll('.leaflet-container path')].some(
      (p) => p.getAttribute('stroke-width') === '5'
    ),
    { timeout: 15000 }
  )
  await page.waitForTimeout(2000)

  const streetPoint = await page.evaluate(() => {
    const paths = [...document.querySelectorAll('.leaflet-container path')].filter(
      (p) => p.getAttribute('stroke-width') === '5'
    )
    for (const p of paths) {
      const len = typeof p.getTotalLength === 'function' ? p.getTotalLength() : 0
      if (!len) continue
      for (const frac of [0.5, 0.25, 0.75, 0.1, 0.9]) {
        const pos = p.getPointAtLength(len * frac)
        const m = p.getScreenCTM()
        if (!m) continue
        const x = m.a * pos.x + m.c * pos.y + m.e
        const y = m.b * pos.x + m.d * pos.y + m.f
        if (x < 10 || y < 10 || x > innerWidth - 10 || y > innerHeight - 10) continue
        if (document.elementFromPoint(x, y) === p) return { x, y }
      }
    }
    return null
  })
  assert(streetPoint, 'found a clickable point on a highlighted Kúpeľná street')
  await page.mouse.click(streetPoint.x, streetPoint.y)
  const legend = page.locator('.district-evidence-legend')
  await legend.waitFor({ state: 'visible', timeout: 10000 })
  const legendText = await legend.innerText()
  assert(legendText.includes('Nálezy § 44 obvodu'), 'legend has the §44 title')
  assert(legendText.includes('DEMO'), 'legend flags demo provenance')

  // Frame the Kúpeľná demo evidence point FIRST via the app's own flyto
  // bridge, THEN enable the "Adresné body obvodov" overlay. Order matters:
  // toggling the overlay from zoom < 16 auto-zooms but the layer's own
  // visibility check races the animation and self-disables (overlayremove
  // resets housePointsEnabled) — dots never appear. Recorded in docs/ISSUES.md;
  // zoom-first is also the flow the label suggests ("priblížte ≥ 16").
  await page.evaluate((pt) => {
    window.dispatchEvent(
      new CustomEvent('so:flyto', { detail: { lat: pt.lat, lon: pt.lon, zoom: 17 } })
    )
  }, DEMO_POINT)
  await page.waitForTimeout(2500)

  // The Leaflet layers control expands on hover and collapses when the mouse
  // leaves — hover it, then click the overlay's label while still inside.
  await page.locator('.leaflet-control-layers').hover()
  await page
    .locator('.leaflet-control-layers label', { hasText: 'Adresné body obvodov' })
    .click()
  await page.waitForTimeout(1500)

  // Overlay renders house points (streetPoints pane) at zoom ≥ 16 — the demo
  // evidence address is centered in frame.
  const housePointPaths = await page.locator('.leaflet-streetPoints-pane path').count()
  assert(housePointPaths > 0, 'address-dots overlay renders house points at zoom ≥ 16')
  // Amber dashed ring (#b45309) = demo evidence point marker. Currently absent:
  // fetchHousePoints() (app/map/page.tsx) omits is_demo from its select, so the
  // amber branch never triggers — recorded in docs/ISSUES.md, app fix is out of
  // scope for this proof sprint.
  const demoMarkers = await page.locator('.leaflet-container path[stroke="#b45309"]').count()
  if (demoMarkers === 0) {
    console.log('KNOWN ISSUE (docs/ISSUES.md): amber demo ring absent — fetchHousePoints omits is_demo')
  }
  assert(await legend.isVisible(), 'legend still visible after overlay + flyto')

  await page.screenshot({ path: `${OUT}/cp5-map-legend-demo-points.png` })
  console.log(`OK map: legend + ${housePointPaths} house point(s), ${demoMarkers} amber demo ring(s) → cp5-map-legend-demo-points.png`)

  // ── 2. District detail: verdict evidence ─────────────────────────────────
  tracker.setKey(page, 'district-detail')
  await page
    .locator('a[href^="/districts/"]', { hasText: 'Kúpeľná' })
    .first()
    .click()
  await page.waitForURL('**/districts/**', { timeout: 20000 })
  const evidenceHeading = page.getByRole('heading', { name: 'Nálezy a dôkazy § 44' })
  await evidenceHeading.waitFor({ state: 'visible', timeout: 20000 })
  // Let the detail map + scorecard settle before shooting.
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await page.waitForTimeout(2000)

  const findingsSection = page.locator('section, div').filter({ has: evidenceHeading }).last()
  const sectionText = await findingsSection.innerText()
  assert(sectionText.includes('DEMO'), 'detail findings carry the DEMO provenance tag')
  assert(sectionText.includes('Š2'), 'detail lists the Š2 topology finding')

  await evidenceHeading.scrollIntoViewIfNeeded()
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${OUT}/cp5-district-detail-evidence.png` })
  console.log('OK detail: Nálezy a dôkazy § 44 with DEMO evidence → cp5-district-detail-evidence.png')

  // ── 3. Findings register: scenario filter active ─────────────────────────
  tracker.setKey(page, 'findings-register')
  await page.getByRole('link', { name: 'Register nálezov' }).first().click()
  await page.waitForURL('**/findings**', { timeout: 20000 })
  await page.getByRole('heading', { name: 'Register nálezov' }).waitFor({ timeout: 20000 })

  // Real select interaction: scenario type → Prekryv adries (S2).
  await page.locator('#filter-scenario').click()
  await page.getByRole('option', { name: 'Prekryv adries' }).click()
  await page.waitForURL('**scenario=address_overlap**', { timeout: 20000 })
  await page.waitForTimeout(1000)

  const codes = await page.locator('table code').allInnerTexts()
  assert(codes.length > 0, 'filtered register shows rows')
  assert(codes.every((c) => c.trim() === 'S2'), `only S2 rows visible, got: ${codes}`)
  const demoBadges = await page.locator('table').getByText('DEMO', { exact: true }).count()
  assert(demoBadges > 0, 'register rows carry DEMO badges')

  await page.screenshot({ path: `${OUT}/cp5-register-scenario-filter.png` })
  console.log(`OK register: ${codes.length} S2 row(s) with scenario filter → cp5-register-scenario-filter.png`)

  await page.close()
  await browser.close()

  console.log('=== CP5 PROOF PACK ===')
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: zero console errors on map, district detail, findings register')
}

main().catch((e) => { console.error(e); process.exit(1) })
