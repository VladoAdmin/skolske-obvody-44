// Sprint 5 regression spec — PostgREST caps unpaginated selects at 1000 rows,
// so /map used to fetch only ~1000 of the 2974 street segments and whole
// neighbourhoods (city centre incl. Hlavná) rendered uncoloured. Asserts:
//   1. the street layer reports >2500 rendered segments (data-street-segments)
//   2. the districts pane really holds >2500 drawn path elements
//   3. the city-centre street "Hlavná" is drawn with a coloured (hsl) line
// Plus the standing §44 gate: ZERO JS console errors. Saves the sprint-5 proof
// screenshot (city centre with coloured streets) to docs/proof/.
import { mkdirSync } from 'fs'
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

const OUT = 'docs/proof'
mkdirSync(OUT, { recursive: true })

// Prešov city centre (Hlavná) — used only to FRAME the proof screenshot via
// the app's own so:flyto bridge, never to assert on coordinates.
const CENTRE = { lat: 48.9985, lon: 21.24 }

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map')

  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)

  // Street layer built → the map container carries the render stat.
  await page.waitForFunction(
    () => Number(document.querySelector('[data-street-segments]')?.getAttribute('data-street-segments')) > 0,
    { timeout: 20000 }
  )

  // 1. Rendered segment count — the actual sprint-5 regression gate. An
  //    unpaginated fetch caps at 1000; the full view has 2974 segments.
  const segments = await page.evaluate(() =>
    Number(document.querySelector('[data-street-segments]')?.getAttribute('data-street-segments'))
  )
  assert(segments > 2500, `street layer reports >2500 segments (PostgREST cap regression), got ${segments}`)

  // 2. Belt and braces: the drawn layers exist in the DOM (Leaflet's SVG
  //    renderer keeps one path element per added street layer).
  const domPaths = await page.locator('.leaflet-districts-pane path').count()
  assert(domPaths > 2500, `districts pane holds >2500 path elements, got ${domPaths}`)

  // 3. City-centre street coloured: Hlavná sat beyond row 1000, so it was one
  //    of the streets the owner saw uncoloured on the live demo.
  // __soStreetColors is keyed by `${district_id}::${street}` (VLA-12 — plain
  // street-name keys collide across districts), so look up by suffix rather
  // than hardcoding the district's DB-generated UUID.
  const hlavnaColor = await page.evaluate(() => {
    const colors = window.__soStreetColors ?? {}
    const key = Object.keys(colors).find((k) => k.endsWith('::Hlavná'))
    return key ? colors[key] : undefined
  })
  assert(
    typeof hlavnaColor === 'string' && hlavnaColor.startsWith('hsl('),
    `"Hlavná" is drawn with an hsl district colour, got ${JSON.stringify(hlavnaColor)}`
  )

  // Proof screenshot: frame the city centre so the coloured Hlavná area is
  // visible (this is exactly the area that rendered uncoloured before).
  await page.evaluate((pt) => {
    window.dispatchEvent(
      new CustomEvent('so:flyto', { detail: { lat: pt.lat, lon: pt.lon, zoom: 15 } })
    )
  }, CENTRE)
  await page.waitForTimeout(2500)
  await page.screenshot({ path: `${OUT}/sprint5-map-centre-streets.png` })
  console.log(`OK map: ${segments} segments fetched, ${domPaths} DOM paths, Hlavná ${hlavnaColor} → sprint5-map-centre-streets.png`)

  await page.close()
  await browser.close()

  console.log('=== SPRINT 5 STREET COVERAGE ===')
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: full street layer rendered, zero console errors')
}

main().catch((e) => { console.error(e); process.exit(1) })
