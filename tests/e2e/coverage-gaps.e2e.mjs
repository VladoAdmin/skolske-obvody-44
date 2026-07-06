// VLA-14 gate — every map "hole" (street with no district colour) is
// explicitly classified and visualised as exactly one of:
//   vzn_gap  — "VZN medzera": in the address register, assigned by no VZN
//              (a real Š1-family § 44 finding, red dashed)
//   data_gap — "Nedostatočné dáta": OSM-only name, cannot be anchored to the
//              register — "neurčené", NEVER presented as a violation (gray
//              dashed)
// Asserts per category: layer counts, a known street's category, the click
// popup wording (incl. the data-gap non-violation guarantee), the legend and
// the summary-strip counters. Plus the standing §44 gate: ZERO console errors.
import { mkdirSync } from 'fs'
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

const OUT = 'docs/proof'
mkdirSync(OUT, { recursive: true })

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map')

  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)

  // Gap layer built → the map container carries the per-category counts.
  await page.waitForFunction(
    () => Number(document.querySelector('[data-vzn-gaps]')?.getAttribute('data-vzn-gaps')) > 0,
    { timeout: 20000 }
  )
  const vznGaps = await page.evaluate(() =>
    Number(document.querySelector('[data-vzn-gaps]')?.getAttribute('data-vzn-gaps'))
  )
  const dataGaps = await page.evaluate(() =>
    Number(document.querySelector('[data-data-gaps]')?.getAttribute('data-data-gaps'))
  )
  assert(vznGaps > 0, `at least one vzn_gap street classified, got ${vznGaps}`)
  assert(dataGaps > 0, `at least one data_gap street classified, got ${dataGaps}`)

  // Known representatives (live register/VZN/OSM state): Tehelná is in the
  // register with no VZN assignment; Bardejovská exists only in OSM.
  const tehelna = await page.evaluate(() => (window.__soGapCategories ?? {})['Tehelná'])
  assert(tehelna === 'vzn_gap', `"Tehelná" classified as vzn_gap, got ${JSON.stringify(tehelna)}`)
  const bardejovska = await page.evaluate(() => (window.__soGapCategories ?? {})['Bardejovská'])
  assert(bardejovska === 'data_gap', `"Bardejovská" classified as data_gap, got ${JSON.stringify(bardejovska)}`)

  // Both categories are DRAWN with distinct styles (dedicated path classes).
  const vznPaths = await page.locator('path.so-gap-vzn').count()
  const dataPaths = await page.locator('path.so-gap-data').count()
  assert(vznPaths > 0, `vzn_gap paths drawn, got ${vznPaths}`)
  assert(dataPaths > 0, `data_gap paths drawn, got ${dataPaths}`)

  // Popup helper: Leaflet keeps a closed popup in the DOM while it fades out,
  // so read the NEWEST popup and, when closing, wait until none remain.
  const readPopup = async () => {
    const p = page.locator('.leaflet-popup-content').last()
    await p.waitFor({ state: 'visible', timeout: 5000 })
    return p.innerText()
  }
  const closePopups = async () => {
    await page.keyboard.press('Escape')
    await page.waitForFunction(
      () => document.querySelectorAll('.leaflet-popup-content').length === 0,
      { timeout: 5000 }
    )
  }

  // [UAT vzn_gap] clicking a red-dashed street opens the explanatory popup:
  // category + why (register presence, no VZN) + § 44 anchoring.
  await page.locator('path.so-gap-vzn').first().dispatchEvent('click')
  let popupText = await readPopup()
  assert(popupText.includes('VZN medzera'), `vzn_gap popup names the category, got: ${popupText.slice(0, 160)}`)
  assert(popupText.includes('žiadne VZN'), 'vzn_gap popup explains no VZN assigns the street')
  assert(popupText.includes('§ 44'), 'vzn_gap popup cites § 44')
  assert(popupText.includes('Register adries: áno'), 'vzn_gap popup shows register evidence')
  await closePopups()

  // [UAT data_gap] clicking a gray-dashed street opens the "neurčené" popup —
  // it must say dátová medzera and explicitly NOT be a violation.
  await page.locator('path.so-gap-data').first().dispatchEvent('click')
  popupText = await readPopup()
  assert(popupText.includes('Nedostatočné dáta'), `data_gap popup names the category, got: ${popupText.slice(0, 160)}`)
  assert(popupText.includes('dátová medzera'), 'data_gap popup says dátová medzera (neurčené)')
  assert(popupText.includes('Nejde o zistené porušenie'), 'data_gap popup explicitly negates a violation')
  await closePopups()

  // Legend carries both entries (md+ viewport in helpers → visible).
  const legend = page.locator('text=VZN medzera — ulica bez obvodu')
  assert(await legend.count() > 0, 'legend has the VZN medzera entry')
  const legendData = page.locator('text=Nedostatočné dáta — neurčené')
  assert(await legendData.count() > 0, 'legend has the Nedostatočné dáta entry')

  // Summary strip shows both counters and they match the layer counts.
  const stripVzn = await page.locator('[data-testid="summary-vzn-gaps"] dd').innerText()
  const stripData = await page.locator('[data-testid="summary-data-gaps"] dd').innerText()
  assert(Number(stripVzn) === vznGaps, `summary strip VZN medzera count ${stripVzn} === layer ${vznGaps}`)
  assert(Number(stripData) === dataGaps, `summary strip Nedostatočné dáta count ${stripData} === layer ${dataGaps}`)

  // Proof screenshot framed on the city (the synthetic popup clicks autoPan
  // the map towards the viewport-corner latlng, so re-frame first) — uses the
  // app's own so:flyto bridge, same as street-coverage.e2e.mjs.
  await page.evaluate(() => {
    window.dispatchEvent(
      new CustomEvent('so:flyto', { detail: { lat: 48.9985, lon: 21.24, zoom: 13 } })
    )
  })
  await page.waitForTimeout(2500)
  await page.screenshot({ path: `${OUT}/vla14-coverage-gaps.png` })
  console.log(`OK map: vzn_gap=${vznGaps} (${vznPaths} paths), data_gap=${dataGaps} (${dataPaths} paths) → vla14-coverage-gaps.png`)

  await page.close()
  await browser.close()

  console.log('=== VLA-14 COVERAGE GAPS ===')
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: both gap categories classified, drawn, explained; zero console errors')
}

main().catch((e) => { console.error(e); process.exit(1) })
