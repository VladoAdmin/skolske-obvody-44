// VLA-14 gate (updated by VLA-20) — every map "hole" (street with no district
// colour) is explicitly classified and visualised as:
//   vzn_gap — "VZN medzera": in the address register, assigned by no VZN
//             (a real Š1-family § 44 finding, red dashed)
// VLA-20 removed the former data_gap ("Nedostatočné dáta") state from the
// product entirely — this spec asserts the state is GONE from the layer, the
// legend, the summary strip and the page text.
// Plus the standing §44 gate: ZERO console errors.
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

  // Gap layer built → the map container carries the count.
  await page.waitForFunction(
    () => Number(document.querySelector('[data-vzn-gaps]')?.getAttribute('data-vzn-gaps')) > 0,
    { timeout: 20000 }
  )
  const vznGaps = await page.evaluate(() =>
    Number(document.querySelector('[data-vzn-gaps]')?.getAttribute('data-vzn-gaps'))
  )
  assert(vznGaps > 0, `at least one vzn_gap street classified, got ${vznGaps}`)

  // Known representative (live register/VZN state): Tehelná is in the
  // register with no VZN assignment.
  const tehelna = await page.evaluate(() => (window.__soGapCategories ?? {})['Tehelná'])
  assert(tehelna === 'vzn_gap', `"Tehelná" classified as vzn_gap, got ${JSON.stringify(tehelna)}`)

  // vzn_gap streets are DRAWN (dedicated path class); the retired data_gap
  // class must not exist anywhere in the DOM.
  const vznPaths = await page.locator('path.so-gap-vzn').count()
  assert(vznPaths > 0, `vzn_gap paths drawn, got ${vznPaths}`)
  const dataPaths = await page.locator('path.so-gap-data').count()
  assert(dataPaths === 0, `no data_gap paths may exist (VLA-20), got ${dataPaths}`)

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
  const popupText = await readPopup()
  assert(popupText.includes('VZN medzera'), `vzn_gap popup names the category, got: ${popupText.slice(0, 160)}`)
  assert(popupText.includes('žiadne VZN'), 'vzn_gap popup explains no VZN assigns the street')
  assert(popupText.includes('§ 44'), 'vzn_gap popup cites § 44')
  assert(popupText.includes('Register adries: áno'), 'vzn_gap popup shows register evidence')
  await closePopups()

  // Legend carries the VZN medzera entry; the retired state is gone.
  const legend = page.locator('text=VZN medzera — ulica bez obvodu')
  assert(await legend.count() > 0, 'legend has the VZN medzera entry')

  // Summary strip counter matches the layer count; no retired-state counter.
  const stripVzn = await page.locator('[data-testid="summary-vzn-gaps"] dd').innerText()
  assert(Number(stripVzn) === vznGaps, `summary strip VZN medzera count ${stripVzn} === layer ${vznGaps}`)
  const stripData = await page.locator('[data-testid="summary-data-gaps"]').count()
  assert(stripData === 0, 'summary strip has no Nedostatočné dáta counter (VLA-20)')

  // The removed state's wording must not appear anywhere on the page.
  const bodyText = await page.locator('body').innerText()
  assert(!/nedostatočné dáta/i.test(bodyText), 'no "nedostatočné dáta" string on /map (VLA-20)')

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
  console.log(`OK map: vzn_gap=${vznGaps} (${vznPaths} paths), data_gap layer absent → vla14-coverage-gaps.png`)

  await page.close()
  await browser.close()

  console.log('=== VLA-14 COVERAGE GAPS ===')
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: vzn gaps classified, drawn, explained; retired data_gap state absent; zero console errors')
}

main().catch((e) => { console.error(e); process.exit(1) })
