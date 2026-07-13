// VLA-32 gate — obce spoločného obvodu (VLA-21/31 shared-municipality
// catchment areas) merged into their owning district's OWN layer: no
// separate toggle, and clicking an area no longer gets its own popup
// clobbered by the parent district's summary popup.
//   [UAT-1] no standalone "Obce spoločného obvodu" row in the layer-control
//           checkbox list (superseded by VLA-21's old UAT-5 — re-asserted
//           here as this ticket's own regression gate).
//   [UAT-2] clicking a shared-municipality-area polygon (Gregorovce) opens
//           ITS OWN popup (grade range) and that popup is NOT replaced by
//           the parent district's summary popup — the actual bug this job
//           fixed (Leaflet's Layer.bindPopup click→openPopup listener on
//           districtGroup was firing for area clicks too, via propagation;
//           fixed via areaLayer.removeEventParent(districtGroup)).
//   [UAT-3] the district's OWN summary popup (with its "Zobraziť detail
//           obvodu" link) still opens correctly via EVENT_SELECT_DISTRICT —
//           proves the fix didn't collaterally break the district's own
//           popup wiring.
//   [UAT-4] toggling that district off (district-toggle-panel checkbox)
//           also removes its shared-municipality areas from the DOM — same
//           on/off toggle, not an independent layer.
//   [UAT-5] district detail page lists its assigned obce (data-driven
//           section added in the VLA-32 commit).
// Plus the standing §44 gate: ZERO console errors.
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

async function findAreaPopup(page, locatorAll, wantedName) {
  const total = await locatorAll.count()
  for (let i = 0; i < total; i++) {
    await locatorAll.nth(i).dispatchEvent('click')
    const popup = page.locator('.leaflet-popup-content').last()
    await popup.waitFor({ state: 'visible', timeout: 5000 })
    const text = await popup.innerText()
    if (text.includes(wantedName)) return { text, index: i }
    await page.keyboard.press('Escape')
    await page.waitForTimeout(400)
  }
  return null
}

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map-vla32')

  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)
  await page.waitForFunction(
    () => document.querySelectorAll('.leaflet-container path').length > 50,
    { timeout: 20000 }
  )
  await page.waitForFunction(
    () => document.querySelectorAll('.so-shared-municipality-area').length > 0,
    { timeout: 10000 }
  )
  await page.waitForTimeout(1500)

  // ── [UAT-1] no standalone layer-control entry ────────────────────────────
  await page.locator('.leaflet-control-layers').hover()
  const checkboxLabel = page.locator('.leaflet-control-layers label', { hasText: 'Obce spoločného obvodu' })
  assert((await checkboxLabel.count()) === 0, 'no standalone layer-control checkbox for shared-municipality areas')
  await page.keyboard.press('Escape')

  // ── [UAT-2] area click opens ITS OWN popup, not clobbered by district ───
  const areas = page.locator('.so-shared-municipality-area')
  const gregorovce = await findAreaPopup(page, areas, 'Gregorovce')
  assert(gregorovce, 'found a polygon popup naming Gregorovce')
  assert(gregorovce.text.includes('Ročníky:'), `area's own popup shows the grade line, got: ${gregorovce.text.slice(0, 200)}`)
  assert(gregorovce.text.includes('Bajkalská'), `area's own popup names its owning school (Bajkalská), got: ${gregorovce.text.slice(0, 200)}`)
  assert(
    !gregorovce.text.includes('Zobraziť detail obvodu'),
    `area's own popup must NOT be replaced by the district summary popup (which carries the "Zobraziť detail obvodu" link), got: ${gregorovce.text.slice(0, 300)}`
  )
  const openPopupCount = await page.locator('.leaflet-popup').count()
  assert(openPopupCount === 1, `exactly one popup open after the area click (no duplicate/stacked popup), got ${openPopupCount}`)
  await page.keyboard.press('Escape')
  await page.waitForTimeout(200)

  // ── [UAT-3] district's own summary popup still works ────────────────────
  const districtButton = page.locator('button', { hasText: 'Bajkalská' }).first()
  assert((await districtButton.count()) >= 1, 'Bajkalská entry present in the district toggle panel')
  await districtButton.click()
  const districtPopup = page.locator('.leaflet-popup-content').last()
  await districtPopup.waitFor({ state: 'visible', timeout: 5000 })
  const districtPopupText = await districtPopup.innerText()
  assert(
    districtPopupText.includes('Zobraziť detail obvodu') || districtPopupText.includes('Bajkalská'),
    `district's own summary popup opens via selectDistrict, got: ${districtPopupText.slice(0, 200)}`
  )
  const detailLink = districtPopup.locator('a', { hasText: 'Zobraziť detail obvodu' })
  assert((await detailLink.count()) === 1, 'district summary popup carries its detail link')
  const districtHref = await detailLink.getAttribute('href')
  const districtId = districtHref?.split('/districts/')[1]
  assert(!!districtId, `district id extracted from detail link href, got: ${districtHref}`)

  // ── [UAT-4] toggling the district off also hides its areas ──────────────
  const districtCheckbox = page.locator('input[type="checkbox"][aria-label*="Bajkalská"]')
  assert((await districtCheckbox.count()) === 1, 'Bajkalská toggle checkbox present in the panel')
  const areasBefore = await page.locator('.so-shared-municipality-area').count()
  assert(areasBefore > 0, 'Bajkalská areas rendered before toggling off')
  await districtCheckbox.uncheck()
  await page.waitForTimeout(300)
  const gregorovcePolygonGone = await page.evaluate(() => {
    const tooltips = Array.from(document.querySelectorAll('.leaflet-tooltip'))
    return !tooltips.some((t) => t.textContent?.includes('Gregorovce'))
  })
  const areasAfter = await page.locator('.so-shared-municipality-area').count()
  assert(areasAfter < areasBefore, `toggling Bajkalská off also removes its shared-municipality areas, before=${areasBefore} after=${areasAfter}`)
  assert(gregorovcePolygonGone, 'Gregorovce (a Bajkalská area) no longer present after toggling the district off')
  await districtCheckbox.check()
  await page.waitForTimeout(300)
  const areasRestored = await page.locator('.so-shared-municipality-area').count()
  assert(areasRestored === areasBefore, `re-checking Bajkalská restores its areas, expected=${areasBefore} got=${areasRestored}`)

  // ── [UAT-5] district detail page lists assigned obce ─────────────────────
  await page.goto(`${BASE}/districts/${districtId}`, { waitUntil: 'domcontentloaded' })
  tracker.setKey(page, 'district-detail-vla32')
  const sharedSection = page.locator('#shared-municipalities-heading')
  await sharedSection.waitFor({ state: 'visible', timeout: 10000 })
  const sharedSectionText = await sharedSection.locator('xpath=..').innerText()
  assert(sharedSectionText.includes('Gregorovce'), `district detail page lists its assigned obce, got: ${sharedSectionText.slice(0, 300)}`)
  assert(sharedSectionText.includes('ročníky'), 'district detail page shows the VZN grade range per obec')

  // ── standing gate: zero console errors ───────────────────────────────────
  const totalErrors = tracker.report()
  assert(totalErrors === 0, `zero console errors, got ${totalErrors}`)

  await page.close()
  await browser.close()
  console.log('\nVLA-32 E2E: ALL ASSERTIONS PASSED (merged layer, no separate toggle, area popup not clobbered, district popup intact, toggle-together, detail page list)')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
