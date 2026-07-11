// VLA-21 gate — obce spoločného obvodu (VZN grades 5-9 / 1-9 pooled
// catchments, e.g. ZŠ Bajkalská + Gregorovce/Hubošovce/Uzovce) render as
// real polygon AREAS, not invisible — the map previously showed nothing for
// them (Vladov PDF zoznam závad, závada 3, 2026-07-06).
//   [UAT-1] /map: shared-municipality areas render by DEFAULT (unlike the
//           OFF-by-default analytical overlays) — exactly 22 polygons
//           (21 distinct municipalities, Dulová Ves shared by 2 districts'
//           catchments — VLA-21 investigation log), className
//           so-shared-municipality-area.
//   [UAT-2] Gregorovce's polygon fill colour (hue) matches its owning
//           district's (Bajkalská) street colour hue — same
//           getDistrictHue() palette, so it visually reads as "part of
//           this district's catchment".
//   [UAT-3] clicking Gregorovce's polygon opens a popup naming the owning
//           school (Bajkalská) and its VZN grade range (5. – 9. ročníka) —
//           data-driven, not hardcoded in the UI.
//   [UAT-4] grade is differentiated per municipality, not per district:
//           within the same district (Československej armády), Malý Šariš
//           (1. – 9. ročníka) and Mirkovce (5. – 9. ročníka) show DIFFERENT
//           grade ranges in their popups.
//   [UAT-5] map legend names this layer (compact group, not one line per
//           municipality) and the layer-control checkbox shows the count.
// Plus the standing §44 gate: ZERO console errors.
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

const EXPECTED_AREA_COUNT = 22 // 21 distinct municipalities, Dulová Ves x2 districts

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
  tracker.attach(page, 'map-shared-municipality-areas')

  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)
  await page.waitForFunction(
    () => document.querySelectorAll('.leaflet-container path').length > 50,
    { timeout: 20000 }
  )
  await page.waitForTimeout(1500)

  // ── [UAT-1] default ON — areas render without any layer toggle ──────────
  await page.waitForFunction(
    () => document.querySelectorAll('.so-shared-municipality-area').length > 0,
    { timeout: 10000 }
  )
  const areaCount = await page.locator('.so-shared-municipality-area').count()
  assert(
    areaCount === EXPECTED_AREA_COUNT,
    `exactly ${EXPECTED_AREA_COUNT} shared-municipality polygons render by default, got ${areaCount}`
  )
  const dataAttr = await page.locator('[data-shared-municipality-areas]').getAttribute('data-shared-municipality-areas')
  assert(dataAttr === String(EXPECTED_AREA_COUNT), `map container reports ${EXPECTED_AREA_COUNT} areas, got ${dataAttr}`)

  // ── [UAT-3] + [UAT-4] click through polygons for Gregorovce + Malý Šariš ─
  const areas = page.locator('.so-shared-municipality-area')
  const found = await findPopupFor(page, areas, ['Gregorovce', 'Malý Šariš', 'Mirkovce'])

  assert(found['Gregorovce'], 'found a polygon popup naming Gregorovce')
  assert(found['Gregorovce'].text.includes('Bajkalská'), `Gregorovce popup names its owning school (Bajkalská), got: ${found['Gregorovce'].text.slice(0, 200)}`)
  assert(found['Gregorovce'].text.includes('5. – 9. ročníka'), `Gregorovce popup shows its VZN grade range, got: ${found['Gregorovce'].text.slice(0, 200)}`)
  assert(found['Gregorovce'].text.includes('Spoločný školský obvod'), 'Gregorovce popup carries the shared-district badge')
  assert(!found['Gregorovce'].text.includes('neuvedené'), 'Gregorovce has an explicit VZN grade — never shown as missing')

  assert(found['Malý Šariš'], 'found a polygon popup naming Malý Šariš')
  assert(found['Mirkovce'], 'found a polygon popup naming Mirkovce')
  assert(found['Malý Šariš'].text.includes('1. – 9. ročníka'), `Malý Šariš popup shows 1.–9. ročníka, got: ${found['Malý Šariš'].text.slice(0, 200)}`)
  assert(found['Mirkovce'].text.includes('5. – 9. ročníka'), `Mirkovce popup shows 5.–9. ročníka, got: ${found['Mirkovce'].text.slice(0, 200)}`)
  assert(
    found['Malý Šariš'].text.match(/1\. – 9\. ročníka/)?.[0] !== found['Mirkovce'].text.match(/5\. – 9\. ročníka/)?.[0]
      ? true
      : false,
    'grade is differentiated per municipality within the same district (Malý Šariš 1.–9. vs Mirkovce 5.–9.), not a single district-level value'
  )

  // ── [UAT-2] Gregorovce's fill hue matches Bajkalská's street hue ────────
  const gregorovceFill = await areas.nth(found['Gregorovce'].index).evaluate(
    (el) => el.getAttribute('fill') || getComputedStyle(el).fill
  )
  const streetColors = await page.evaluate(() => window.__soStreetColors)
  const bajkalskaStreetColor = streetColors?.['Genplk. Jána Ambruša']
  assert(!!bajkalskaStreetColor, 'Bajkalská street colour is exposed for comparison (window.__soStreetColors)')
  const hueOf = (s) => s?.match(/hsl\(\s*(\d+)/)?.[1]
  const gregorovceHue = hueOf(gregorovceFill)
  const bajkalskaHue = hueOf(bajkalskaStreetColor)
  assert(!!gregorovceHue && !!bajkalskaHue, `both colours are hsl() with a parseable hue (area=${gregorovceFill}, street=${bajkalskaStreetColor})`)
  assert(
    gregorovceHue === bajkalskaHue,
    `Gregorovce's polygon hue (${gregorovceHue}) matches its owning district's street hue (${bajkalskaHue})`
  )

  // ── [UAT-5] legend + layer-control checkbox name this layer ─────────────
  const legendText = await page.locator('text=Legenda:').locator('xpath=..').innerText()
  assert(legendText.includes('Obce spoločného obvodu'), 'static legend names the shared-municipality-areas layer')

  await page.locator('.leaflet-control-layers').hover()
  const checkboxLabel = page.locator('.leaflet-control-layers label', { hasText: 'Obce spoločného obvodu' })
  assert((await checkboxLabel.count()) === 1, 'layer-control checkbox for the shared-municipality-areas layer present')
  const checkboxText = await checkboxLabel.innerText()
  assert(checkboxText.includes(String(EXPECTED_AREA_COUNT)), `layer-control checkbox shows the area count, got: ${checkboxText}`)

  // ── standing gate: zero console errors ───────────────────────────────────
  const totalErrors = tracker.report()
  assert(totalErrors === 0, `zero console errors, got ${totalErrors}`)

  await page.close()
  await browser.close()
  console.log(`\nVLA-21 E2E: ALL ASSERTIONS PASSED (${areaCount} shared-municipality areas, Gregorovce popup + colour + legend verified)`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
