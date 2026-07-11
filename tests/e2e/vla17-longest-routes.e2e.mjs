// VLA-17 gate — 5 najdlhších peších trás na obvod + prímestská doprava
// (Vlado, Telegram General #494, 2026-07-06): comparison/overview only, NO
// pass/fail threshold — replaces the earlier prah-based P-b approach.
//   [UAT-1] /map: "5 najdlhších trás" layer is OFF by default; toggling it
//           renders exactly 60 real route polylines (12 districts x 5,
//           className so-longest-route).
//   [UAT-2] the demo district (Bajkalská, the job's own shared-district
//           example) has a route popup with district name, rank badge,
//           origin, and real distance/time from Google Maps.
//   [UAT-3] the summary section "Najdlhšie trasy podľa obvodov" lists
//           Bajkalská's 5 routes, and at least one shared-municipality
//           origin shows a transit alternative (line/time, or an honest
//           "dáta nedostupné" — never silently omitted).
//   [UAT-4] no verdict/threshold vocabulary anywhere in the routes layer or
//           summary section — this feature carries no pass/fail of its own.
// Plus the standing §44 gate: ZERO console errors.
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

// Specific verdict-badge strings (lib/compliance/colors.ts COLOR_LABELS_SK),
// not the bare substring "súlad" — this feature's own honest disclaimer text
// ("Porovnanie, nie hodnotenie súladu") legitimately contains that root word
// while explicitly saying it is NOT a verdict; only literal badge/verdict
// vocabulary is forbidden here.
const FORBIDDEN_VERDICT_WORDS = ['PASS', 'FAIL', 'V súlade', 'Nesúlad', 'verdikt', 'porušenie']

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map-longest-routes')

  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)
  await page.waitForFunction(
    () => document.querySelectorAll('.leaflet-container path').length > 50,
    { timeout: 20000 }
  )
  await page.waitForTimeout(1500)

  // Precondition: routes layer OFF by default, nothing rendered yet.
  assert((await page.locator('.so-longest-route').count()) === 0, 'no route polylines rendered before layer toggle')

  // ── [UAT-1] toggle "5 najdlhších trás" → 60 route polylines ─────────────
  await page.locator('.leaflet-control-layers').hover()
  await page
    .locator('.leaflet-control-layers label', { hasText: 'najdlhších trás' })
    .click()

  await page.waitForFunction(
    () => document.querySelectorAll('.so-longest-route').length > 0,
    { timeout: 10000 }
  )
  const routeCount = await page.locator('.so-longest-route').count()
  assert(routeCount === 60, `exactly 60 route polylines render (12 districts x 5), got ${routeCount}`)

  // ── [UAT-2] demo district (Bajkalská) route popup ────────────────────────
  const dataAttr = await page.locator('[data-longest-routes]').getAttribute('data-longest-routes')
  assert(dataAttr === '60', `map container reports 60 longest routes, got ${dataAttr}`)

  // Open each route's popup via a real click dispatch (polylines are thin,
  // coordinate clicks are flaky — same approach as vla16-mrk-area.e2e.mjs)
  // until we hit one whose popup names the demo district.
  let bajkalskaPopupText = null
  const total = await page.locator('.so-longest-route').count()
  for (let i = 0; i < total; i++) {
    await page.locator('.so-longest-route').nth(i).dispatchEvent('click')
    const popup = page.locator('.leaflet-popup-content').last()
    await popup.waitFor({ state: 'visible', timeout: 5000 })
    const text = await popup.innerText()
    if (text.includes('Bajkalská')) {
      bajkalskaPopupText = text
      break
    }
    await page.keyboard.press('Escape')
  }
  assert(bajkalskaPopupText !== null, 'found a route popup for the demo district (Bajkalská)')
  assert(bajkalskaPopupText.includes('najdlhšia trasa'), `popup shows the rank badge, got: ${bajkalskaPopupText.slice(0, 200)}`)
  assert(bajkalskaPopupText.includes('km'), 'popup shows real distance (km)')
  assert(bajkalskaPopupText.includes('min'), 'popup shows real duration (min)')
  assert(bajkalskaPopupText.includes('Google Maps'), 'popup attributes the route to Google Maps (real routing, not straight-line)')

  // ── [UAT-3] summary section lists Bajkalská + a transit alternative ─────
  await page.locator('#longest-routes-heading').scrollIntoViewIfNeeded()
  const summaryHeading = page.locator('#longest-routes-heading')
  assert((await summaryHeading.count()) === 1, 'summary section heading present')

  const bajkalskaSummary = page.locator('summary', { hasText: 'Bajkalská' })
  assert((await bajkalskaSummary.count()) === 1, 'Bajkalská row present in the summary section')
  await bajkalskaSummary.first().click()
  const bajkalskaList = bajkalskaSummary.first().locator('xpath=../ol')
  await bajkalskaList.waitFor({ state: 'visible', timeout: 5000 })
  const listText = await bajkalskaList.innerText()
  const routeLines = listText.split('\n').filter((l) => l.trim().length > 0)
  assert(routeLines.length === 5, `Bajkalská summary lists exactly 5 routes, got ${routeLines.length}`)
  assert(listText.includes('susedná obec'), 'at least one route is from a shared municipality')
  assert(
    listText.includes('prímestská doprava'),
    'at least one shared-municipality route shows a transit alternative (line/time or honest "dáta nedostupné")'
  )

  // ── [UAT-4] no verdict/threshold vocabulary in this feature's own output ─
  const routesSectionText = await page.locator('section', { has: page.locator('#longest-routes-heading') }).innerText()
  for (const word of FORBIDDEN_VERDICT_WORDS) {
    assert(!routesSectionText.includes(word), `summary section carries no verdict word "${word}"`)
  }
  assert(!bajkalskaPopupText.match(/PASS|FAIL|nesúlad|verdikt/i), 'route popup carries no verdict wording')

  // ── standing gate: zero console errors ───────────────────────────────────
  const totalErrors = tracker.report()
  assert(totalErrors === 0, `zero console errors, got ${totalErrors}`)

  await page.close()
  await browser.close()
  console.log(`\nVLA-17 E2E: ALL ASSERTIONS PASSED (${routeCount} routes, Bajkalská popup + summary verified)`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
