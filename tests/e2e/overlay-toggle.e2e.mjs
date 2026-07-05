// Sprint-4 regression spec for docs/ISSUES.md #1 (real Chrome).
//   #1 Toggling "Adresné body obvodov" from the initial city zoom (< 16) must
//      auto-zoom to 16 and RENDER the dots — before the fix, the programmatic
//      removeLayer inside updateHousePointsVisibility fired overlayremove,
//      which reset housePointsEnabled and the dots never appeared.
// The toggle-from-low-zoom ORDER is the whole point of this spec; the proof
// pack intentionally zooms first, so it can never regress on #1.
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

const HOUSE_DOTS = '.leaflet-streetPoints-pane path'

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map-overlay-toggle')

  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)
  await page.waitForFunction(
    () => document.querySelectorAll('.leaflet-container path').length > 50,
    { timeout: 20000 }
  )
  // Let fitBounds settle at the initial city-level zoom (< 16).
  await page.waitForTimeout(2000)

  // Precondition: overlay off, no address dots rendered.
  assert(
    (await page.locator(HOUSE_DOTS).count()) === 0,
    'no address dots before the overlay is toggled'
  )

  // Toggle the overlay AT the initial zoom — the buggy order from ISSUES.md #1.
  await page.locator('.leaflet-control-layers').hover()
  await page
    .locator('.leaflet-control-layers label', { hasText: 'Adresné body obvodov' })
    .click()

  // Auto-zoom (overlayadd → setZoom(16)) → zoomend re-check must ADD the
  // layer: dots appear with no further user action.
  await page.waitForFunction(
    (sel) => document.querySelectorAll(sel).length > 0,
    HOUSE_DOTS,
    { timeout: 15000 }
  )
  const dots = await page.locator(HOUSE_DOTS).count()
  assert(dots > 0, 'address dots render after toggling from zoom < 16')

  // The layer must STAY on (the race used to self-disable it).
  await page.waitForTimeout(2000)
  assert(
    (await page.locator(HOUSE_DOTS).count()) === dots,
    'address dots stay rendered after the zoom animation settles'
  )

  await page.close()
  await browser.close()

  console.log(`OK overlay toggle from city zoom: ${dots} dot(s)`)
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: overlay-toggle regression spec, zero console errors')
}

main().catch((e) => { console.error(e); process.exit(1) })
