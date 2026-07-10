// VLA-16 gate — MRK localities render as area/streets, not a bare point
// (client feedback 2026-07-06, Telegram General #437):
//   [UAT-1] /map: toggling "MRK lokality — plocha" renders a hatched AREA
//           (so-mrk-area) for every locality, never just a lone dot — the
//           small label-anchor dot (so-mrk-anchor) may ALSO be present, but
//           the area must always accompany it.
//   [UAT-2] the Šrobárova P-e demo scenario draws exactly one exclusion link
//           (so-mrk-exclusion-link) from the locality to its assigned
//           district's school, with a popup naming both the assigned
//           district (Šrobárova) and the geographically-real one
//           (Prostějovská) plus the air-line evidence, DEMO-badged.
//   [UAT-3] map legend explains both the area rendering and the exclusion
//           link.
// Plus the standing §44 gate: ZERO console errors.
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map-mrk-area')

  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)
  await page.waitForFunction(
    () => document.querySelectorAll('.leaflet-container path').length > 50,
    { timeout: 20000 }
  )
  await page.waitForTimeout(1500)

  // Precondition: MRK layer OFF by default, no MRK shapes rendered yet.
  assert((await page.locator('.so-mrk-area').count()) === 0, 'no MRK area rendered before layer toggle')

  // ── [UAT-1] toggle "MRK lokality — plocha" → area, never a bare point ────
  await page.locator('.leaflet-control-layers').hover()
  await page
    .locator('.leaflet-control-layers label', { hasText: 'MRK lokality — plocha' })
    .click()

  await page.waitForFunction(
    () => document.querySelectorAll('.so-mrk-area').length > 0,
    { timeout: 10000 }
  )
  const areaCount = await page.locator('.so-mrk-area').count()
  const anchorCount = await page.locator('.so-mrk-anchor').count()
  assert(areaCount > 0, `MRK area shapes render (got ${areaCount})`)
  assert(
    anchorCount === areaCount,
    `every MRK locality has both an area and a label-anchor point (area=${areaCount}, anchor=${anchorCount})`
  )
  // The area path must actually use the hatch fill, not a plain dot fill.
  const hatchFillCount = await page.locator('.so-mrk-area[fill="url(#mrkHatch)"]').count()
  assert(hatchFillCount === areaCount, 'every MRK area uses the hatched fill pattern')

  // ── [UAT-2] Šrobárova exclusion link + popup ─────────────────────────────
  const linkCount = await page.locator('.so-mrk-exclusion-link').count()
  assert(linkCount === 1, `exactly one exclusion link for the seeded Šrobárova/Prostějovská demo (got ${linkCount})`)

  await page.locator('.so-mrk-exclusion-link').first().dispatchEvent('click')
  const popup = page.locator('.leaflet-popup-content').last()
  await popup.waitFor({ state: 'visible', timeout: 5000 })
  const popupText = await popup.innerText()
  assert(popupText.includes('vyčlenenie'), `popup names the exclusion, got: ${popupText.slice(0, 200)}`)
  assert(popupText.includes('Šrobárova'), 'popup names the assigned district (Šrobárova)')
  assert(popupText.includes('Prostějovská'), 'popup names the geographically-real district (Prostějovská)')
  assert(popupText.includes('DEMO'), 'popup carries the DEMO badge (fabricated assignment, real geometry)')
  assert(popupText.includes('km'), 'popup shows the air-line distance evidence')
  assert(popupText.includes('P-e'), 'popup attributes the finding to P-e (sociálny kontext)')

  // ── [UAT-3] legend explains the new rendering ────────────────────────────
  const legendText = await page.locator('p', { hasText: 'Legenda:' }).first().innerText()
  assert(legendText.includes('MRK lokalita — plocha'), 'legend describes MRK as an area, not a point')
  assert(legendText.includes('Vyčlenenie'), 'legend explains the exclusion link')

  // ── standing gate: zero console errors ───────────────────────────────────
  const totalErrors = tracker.report()
  assert(totalErrors === 0, `zero console errors, got ${totalErrors}`)

  await page.close()
  await browser.close()
  console.log(`\nVLA-16 E2E: ALL ASSERTIONS PASSED (${areaCount} MRK area(s), ${linkCount} exclusion link)`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
