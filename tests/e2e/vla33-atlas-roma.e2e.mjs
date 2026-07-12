// VLA-33 gate — REAL Atlas rómskych komunít 2019 (ÚSVRK) municipality-level
// Roma-population-share layer, Okres Prešov, threshold-filtered:
//   [UAT-1] /map: layer OFF by default (same treatment as the DEMO MRK
//           overlay — opt-in via the layer control), toggling
//           "Segregovaná menšina — Atlas ÚSVRK 2019" renders exactly 22
//           real municipality polygons (so-atlas-roma-area), matching
//           so_atlas_roma_municipalities live (32 ingested, 22 pass the
//           configured >20% threshold).
//   [UAT-2] Kendice's popup shows its % share band, is explicitly labelled
//           "reálne dáta" (never DEMO), names its assigned školský obvod
//           (Základná škola, Májové námestie č. 1 — via the VZN shared-
//           catchment link) and cites the Atlas source + download date.
//   [UAT-3] a municipality with NO known assignment in this app's district
//           data (Červenica) shows that honestly ("nie je súčasťou..."),
//           never a fabricated obvod.
//   [UAT-4] map legend + layer-control checkbox name this layer distinctly
//           from "MRK lokalita" (DEMO) — a viewer must never confuse them.
// Plus the standing §44 gate: ZERO console errors.
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

const EXPECTED_AREA_COUNT = 22

async function findPopupFor(page, locatorAll, wantedNames) {
  const found = {}
  const total = await locatorAll.count()
  for (let i = 0; i < total && Object.keys(found).length < wantedNames.length; i++) {
    await locatorAll.nth(i).dispatchEvent('click')
    const popup = page.locator('.leaflet-popup-content').last()
    await popup.waitFor({ state: 'visible', timeout: 5000 })
    const text = await popup.innerText()
    for (const name of wantedNames) {
      if (!found[name] && text.includes(name)) found[name] = { text, index: i }
    }
    await page.keyboard.press('Escape')
  }
  return found
}

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map-atlas-roma')

  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)
  await page.waitForFunction(
    () => document.querySelectorAll('.leaflet-container path').length > 50,
    { timeout: 20000 }
  )
  await page.waitForTimeout(1500)

  // Precondition: OFF by default, no shapes rendered yet.
  assert((await page.locator('.so-atlas-roma-area').count()) === 0, 'no Atlas Roma area rendered before layer toggle')

  // ── [UAT-1] toggle the layer on ──────────────────────────────────────────
  await page.locator('.leaflet-control-layers').hover()
  await page
    .locator('.leaflet-control-layers label', { hasText: 'Segregovaná menšina — Atlas ÚSVRK 2019' })
    .click()

  await page.waitForFunction(
    () => document.querySelectorAll('.so-atlas-roma-area').length > 0,
    { timeout: 10000 }
  )
  const areaCount = await page.locator('.so-atlas-roma-area').count()
  assert(
    areaCount === EXPECTED_AREA_COUNT,
    `exactly ${EXPECTED_AREA_COUNT} Atlas Roma-share polygons render, got ${areaCount}`
  )
  const dataAttr = await page.locator('[data-atlas-roma-municipalities]').getAttribute('data-atlas-roma-municipalities')
  assert(dataAttr === String(EXPECTED_AREA_COUNT), `map container reports ${EXPECTED_AREA_COUNT} municipalities, got ${dataAttr}`)

  // ── [UAT-2] + [UAT-3] popups for Kendice (known obvod) + Červenica (none) ─
  const areas = page.locator('.so-atlas-roma-area')
  const found = await findPopupFor(page, areas, ['Kendice', 'Červenica'])

  assert(found['Kendice'], 'found a polygon popup naming Kendice')
  assert(/\d{1,3}%-\d{1,3}%/.test(found['Kendice'].text), `Kendice popup shows its % share band, got: ${found['Kendice'].text.slice(0, 200)}`)
  assert(found['Kendice'].text.includes('reálne dáta'), 'Kendice popup is explicitly labelled real data')
  assert(!found['Kendice'].text.includes('DEMO'), 'Kendice popup never carries a DEMO badge — this is real government data')
  assert(found['Kendice'].text.includes('Základná škola, Májové námestie č. 1'), `Kendice popup names its assigned školský obvod, got: ${found['Kendice'].text.slice(0, 300)}`)
  assert(found['Kendice'].text.includes('Atlas rómskych komunít 2019'), 'Kendice popup cites the Atlas source')
  assert(/stiahnuté \d{4}-\d{2}-\d{2}/.test(found['Kendice'].text), 'Kendice popup cites a download date')

  assert(found['Červenica'], 'found a polygon popup naming Červenica')
  assert(
    found['Červenica'].text.includes('nie je súčasťou žiadneho evidovaného obvodu'),
    `Červenica (no known VZN assignment) shows that honestly, not a fabricated obvod — got: ${found['Červenica'].text.slice(0, 300)}`
  )

  // ── [UAT-4] legend + layer-control distinctly name this layer ───────────
  const legendText = await page.locator('p', { hasText: 'Legenda:' }).first().innerText()
  assert(legendText.includes('Atlas rómskych komunít 2019'), 'static legend names the real Atlas layer')
  assert(legendText.includes('reálne dáta'), 'static legend labels it real data')
  assert(legendText.includes('MRK lokalita — plocha'), 'static legend still separately names the DEMO MRK layer')

  const checkboxLabel = page.locator('.leaflet-control-layers label', { hasText: 'Segregovaná menšina — Atlas ÚSVRK 2019' })
  assert((await checkboxLabel.count()) === 1, 'layer-control checkbox for the Atlas Roma layer present')
  const checkboxText = await checkboxLabel.innerText()
  assert(checkboxText.includes(String(EXPECTED_AREA_COUNT)), `layer-control checkbox shows the municipality count, got: ${checkboxText}`)
  assert(checkboxText.includes('reálne dáta'), 'layer-control checkbox itself is labelled real data')

  // Screenshot proof — layer visibly toggled on, Kendice popup open (% share
  // + real-data badge + assigned obvod), layer-control panel collapsed so
  // the highlighted polygon itself is visible rather than hidden under it.
  await areas.nth(found['Kendice'].index).dispatchEvent('click')
  await page.locator('.leaflet-popup-content').last().waitFor({ state: 'visible', timeout: 5000 })
  await page.mouse.move(200, 200)
  await page.waitForTimeout(300)
  await page.screenshot({ path: 'docs/proof/vla33-atlas-roma.png' })

  // ── standing gate: zero console errors ───────────────────────────────────
  const totalErrors = tracker.report()
  assert(totalErrors === 0, `zero console errors, got ${totalErrors}`)

  await page.close()
  await browser.close()
  console.log(`\nVLA-33 E2E: ALL ASSERTIONS PASSED (${areaCount} real Atlas Roma-share municipalities)`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
