// VLA-20 gate — client defect report 2026-07-06 (defects 7, 2, 4):
//   [UAT-1] /map side panel holds ONLY the district list (no findings in it)
//   [UAT-2] findings are usable WHILE the district list is visible (own
//           full-width panel below the map; click → map fly-to still works)
//   [UAT-3] the string "nedostatočné dáta" appears NOWHERE in the GUI
//           (/map, district detail, /o-metodike, /findings)
//   [UAT-4] the "Expert: Adresné body" layer is DELETED from the district
//           detail map's layer control
//   [UAT-5] the mock barrier (fictional railway) is visible on /map with a
//           DEMO badge
// Plus the standing §44 gate: ZERO console errors on every page visited.
import { mkdirSync } from 'fs'
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

const OUT = 'docs/proof'
mkdirSync(OUT, { recursive: true })

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map')

  // ── /map ──────────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)

  // [UAT-1] side panel = district list only. The DistrictTogglePanel header
  // ("Obvody (N)", a collapsible button with aria-expanded — NOT the hidden
  // mobile tab of the same name) is present; the panel contains no findings
  // header and no severity filter chips (those now live in the separate
  // findings section).
  const districtHeader = page.locator('button[aria-expanded]', { hasText: /^Obvody \(\d+\)/ })
  assert(await districtHeader.count() > 0, 'district panel header "Obvody (N)" present')
  const districtCheckboxes = await page.locator('input[type="checkbox"][aria-label^="Zobraziť obvod"]').count()
  assert(districtCheckboxes >= 12, `district list shows all districts, got ${districtCheckboxes}`)

  // [UAT-2] the findings section exists as its OWN region below the map and is
  // visible at the same time as the district list — no tab switch, no
  // collapse needed.
  const findingsSection = page.locator('section[aria-label="Nálezy"]')
  assert(await findingsSection.count() === 1, 'findings section exists')
  assert(await findingsSection.isVisible(), 'findings section is visible')
  assert(await districtHeader.first().isVisible(), 'district list visible at the same time')
  // Findings panel must NOT contain the district toggle list anymore.
  const togglesInsideFindings = await findingsSection
    .locator('input[type="checkbox"][aria-label^="Zobraziť obvod"]').count()
  assert(togglesInsideFindings === 0, 'no district toggles inside the findings panel')
  // Findings are usable: clicking an item marks it selected (fly-to fires).
  const firstFinding = findingsSection.locator('ul li button').first()
  assert(await firstFinding.count() > 0, 'at least one finding listed')
  await firstFinding.click()
  await page.waitForTimeout(500)
  assert(
    (await findingsSection.locator('text=Zvýraznené na mape').count()) > 0,
    'clicked finding shows the map-highlight hint (fly-to wired)'
  )
  assert(await districtHeader.first().isVisible(), 'district list STILL visible after using findings')

  // [UAT-5] mock barrier drawn with DEMO badge. Layer is on by default.
  const barrierPaths = await page.locator('path.so-barrier').count()
  assert(barrierPaths > 0, `mock barrier drawn on the map, got ${barrierPaths} paths`)
  await page.locator('path.so-barrier').first().dispatchEvent('click')
  const barrierPopup = page.locator('.leaflet-popup-content').last()
  await barrierPopup.waitFor({ state: 'visible', timeout: 5000 })
  const barrierText = await barrierPopup.innerText()
  assert(barrierText.includes('DEMO'), `barrier popup carries the DEMO badge, got: ${barrierText.slice(0, 160)}`)
  assert(/želez/i.test(barrierText), 'barrier popup names the railway')
  await page.keyboard.press('Escape')

  // [UAT-3] no "nedostatočné dáta" anywhere on /map.
  const mapBody = await page.locator('body').innerText()
  assert(!/nedostatočné dáta/i.test(mapBody), 'no "nedostatočné dáta" on /map')

  await page.screenshot({ path: `${OUT}/vla20-map-panel-findings-barrier.png` })
  console.log('OK /map: districts-only panel, findings section usable alongside, DEMO barrier visible')

  // ── district detail: Expert layer deleted, no retired state ──────────────
  tracker.setKey(page, 'district-detail')
  const detailHref = await page.locator('a[href^="/districts/"]').first().getAttribute('href')
  assert(detailHref, 'a district detail link exists on /map')
  await page.goto(`${BASE}${detailHref}`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)
  // Expand the layer control so labels are in the DOM text.
  const layersToggle = page.locator('.leaflet-control-layers-toggle').first()
  if (await layersToggle.count() > 0) {
    await layersToggle.hover().catch(() => {})
  }
  const layersText = await page.locator('.leaflet-control-layers').first().innerText().catch(() => '')
  assert(!/Expert: Adresné body/i.test(layersText), '[UAT-4] Expert: Adresné body layer absent from layer control')
  assert(!/geokódovanie/i.test(layersText), '[UAT-4] no Google-geocoding layer label remains')
  const detailBody = await page.locator('body').innerText()
  assert(!/nedostatočné dáta/i.test(detailBody), 'no "nedostatočné dáta" on district detail')
  await page.screenshot({ path: `${OUT}/vla20-district-detail-no-expert-layer.png` })
  console.log('OK district detail: Expert: Adresné body layer deleted')

  // ── /o-metodike and /findings: retired state absent ──────────────────────
  tracker.setKey(page, 'o-metodike')
  await page.goto(`${BASE}/o-metodike`, { waitUntil: 'domcontentloaded' })
  const metodikaBody = await page.locator('body').innerText()
  assert(!/nedostatočné dáta/i.test(metodikaBody), 'no "nedostatočné dáta" on /o-metodike')
  assert(!/INSUFFICIENT_DATA/.test(metodikaBody), 'no INSUFFICIENT_DATA on /o-metodike')
  assert(!/INCOMPLETE/.test(metodikaBody), 'no INCOMPLETE on /o-metodike')

  tracker.setKey(page, 'findings')
  await page.goto(`${BASE}/findings`, { waitUntil: 'domcontentloaded' })
  const findingsBody = await page.locator('body').innerText()
  assert(!/nedostatočné dáta/i.test(findingsBody), 'no "nedostatočné dáta" on /findings')
  console.log('OK /o-metodike + /findings: retired state absent')

  await page.close()
  await browser.close()

  console.log('=== VLA-20 UI CLEANUP ===')
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: all VLA-20 UATs green; zero console errors')
}

main().catch((e) => { console.error(e); process.exit(1) })
