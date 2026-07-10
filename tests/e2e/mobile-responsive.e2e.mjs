// VLA-16 follow-up gate — mobile responsive audit (client report 2026-07-09):
//   [UAT-1] SummaryStrip (/map) does not overlap its own rows at 375px —
//           semafor breakdown and aggregate counts stack vertically instead
//           of rendering on top of each other; unchanged side-by-side at
//           >=640px (commit e110679).
//   [UAT-2] the "← Späť na Slovensko" / home buttons never overlap the
//           Leaflet zoom control at 375px or 768px (commit ab81a31).
// Plus the standing §44 gate: ZERO console errors.
import { chromium } from 'playwright'
import { BASE, CHROME, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

function rectsOverlap(a, b) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y
}

async function launchAt(width, height) {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1.4 })
  return { browser, ctx }
}

async function main() {
  const tracker = makeErrorTracker()

  // ── [UAT-1] SummaryStrip: stacked at 375px, side-by-side at >=640px ───────
  {
    const { browser, ctx } = await launchAt(375, 812)
    const page = await ctx.newPage()
    tracker.attach(page, 'summary-strip-375')
    await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('.leaflet-container', { timeout: 20000 })
    await dismissDemoModal(page)

    const strip = page.locator('section[aria-label="Súhrnný prehľad pilotu"]')
    assert(await strip.count() === 1, 'SummaryStrip present')
    const semaforList = strip.locator('ul').first()
    const aggregateDl = strip.locator('dl').first()
    const semaforBox = await semaforList.boundingBox()
    const aggregateBox = await aggregateDl.boundingBox()
    assert(semaforBox && aggregateBox, 'both SummaryStrip rows have a bounding box at 375px')
    assert(
      !rectsOverlap(semaforBox, aggregateBox),
      `SummaryStrip rows must not overlap at 375px: semafor=${JSON.stringify(semaforBox)} aggregate=${JSON.stringify(aggregateBox)}`
    )
    assert(
      aggregateBox.y >= semaforBox.y + semaforBox.height - 1,
      'aggregate row stacks BELOW the semafor row at 375px (flex-col)'
    )
    console.log('OK SummaryStrip: no row overlap at 375px, stacked vertically')

    await page.close()
    await browser.close()
  }

  // ── [UAT-1b] SummaryStrip: unchanged side-by-side layout at 768px ─────────
  {
    const { browser, ctx } = await launchAt(768, 1024)
    const page = await ctx.newPage()
    tracker.attach(page, 'summary-strip-768')
    await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('.leaflet-container', { timeout: 20000 })
    await dismissDemoModal(page)

    const strip = page.locator('section[aria-label="Súhrnný prehľad pilotu"]')
    const semaforBox = await strip.locator('ul').first().boundingBox()
    const aggregateBox = await strip.locator('dl').first().boundingBox()
    assert(semaforBox && aggregateBox, 'both SummaryStrip rows have a bounding box at 768px')
    // Side-by-side: the two rows share (roughly) the same top y, not stacked.
    assert(
      Math.abs(semaforBox.y - aggregateBox.y) < 4,
      `SummaryStrip rows must stay side-by-side at 768px: semafor.y=${semaforBox.y} aggregate.y=${aggregateBox.y}`
    )
    console.log('OK SummaryStrip: unchanged side-by-side layout at 768px')

    await page.close()
    await browser.close()
  }

  // ── [UAT-2] zoom control vs back/home buttons, 375px + 768px ──────────────
  for (const [width, height] of [[375, 812], [768, 1024]]) {
    const { browser, ctx } = await launchAt(width, height)
    const page = await ctx.newPage()
    tracker.attach(page, `zoom-control-${width}`)
    await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('.leaflet-container', { timeout: 20000 })
    await dismissDemoModal(page)

    const backButton = page.getByRole('button', { name: 'Späť na prehľad Slovenska' })
    const zoomControl = page.locator('.leaflet-control-zoom').first()
    assert(await backButton.count() === 1, `back button present at ${width}px (default PSK mode)`)
    assert(await zoomControl.count() === 1, `Leaflet zoom control present at ${width}px`)

    const backBox = await backButton.boundingBox()
    const zoomBox = await zoomControl.boundingBox()
    assert(backBox && zoomBox, `both controls have a bounding box at ${width}px`)
    assert(
      !rectsOverlap(backBox, zoomBox),
      `back button must not overlap zoom control at ${width}px: back=${JSON.stringify(backBox)} zoom=${JSON.stringify(zoomBox)}`
    )
    console.log(`OK zoom control vs back button: no overlap at ${width}px`)

    await page.close()
    await browser.close()
  }

  console.log('=== MOBILE RESPONSIVE (VLA-16 follow-up) ===')
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: SummaryStrip + zoom-control mobile fixes verified; zero console errors')
}

main().catch((e) => { console.error(e); process.exit(1) })
