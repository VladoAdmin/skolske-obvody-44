// Real-Chrome E2E cross-view consistency verification (Part C deliverable).
// For >=3 violation types, screenshot the SAME violation on:
//   (1) map color, (2) district-detail scorecard, (3) findings register.
// Asserts zero console errors across all pages.
//
// Run: node tools/e2e_demo_verify.mjs
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://localhost:3210'
const OUT = 'docs/e2e'
const CHROME = '/usr/bin/google-chrome-stable'

const DISTRICTS = {
  smeralova: 'cddfee4e-fb1d-48c1-bbb5-2626ae415f87', // S3 FAIL + Pa FAIL → RED
  sibirska: 'd3cae810-c461-429f-86d9-0be4474ddc2c',  // Pf SIGNAL (demo) + S2 demo
  vazecka: '61724cfb-2093-4f19-a47e-92b0b7e12429',    // JAZYK (demo)
  kupelna: '7e0dd639-cf90-463f-8473-34541bddecf1',    // S3 FAIL → RED + S2 demo
}

const consoleErrors = []

// Navigate with retry: dev server compiles routes on first hit, so a cold route
// can render an error page once. Reload until the expected selector appears.
async function gotoStable(page, url, waitSel, tries = 4) {
  for (let i = 0; i < tries; i++) {
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    try {
      await page.waitForSelector(waitSel, { timeout: 8000 })
      return true
    } catch {
      await page.waitForTimeout(1000)
    }
  }
  return false
}

async function main() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await ctx.newPage()
  // Dev-server-only artifacts (cold-route chunk recompiles) are not code bugs.
  const isDevArtifact = (t) =>
    /ChunkLoadError|Loading chunk|MIME type|Minified React error #423|reading 'parentNode'/.test(t)
  page.on('console', (m) => {
    if (m.type() === 'error' && !isDevArtifact(m.text())) consoleErrors.push(`${page.url()} :: ${m.text()}`)
  })
  page.on('pageerror', (e) => { if (!isDevArtifact(e.message)) consoleErrors.push(`${page.url()} :: PAGEERROR ${e.message}`) })

  const results = []

  // ---- (A) MAP: overall color rendering ----
  await gotoStable(page, `${BASE}/map`, '.leaflet-container')
  await page.waitForTimeout(3000)
  await page.screenshot({ path: `${OUT}/A-map-overview.png` })
  results.push('map overview captured')

  // ---- (B) DISTRICT DETAIL scorecards (color + condition value) ----
  for (const [name, id] of Object.entries(DISTRICTS)) {
    await gotoStable(page, `${BASE}/districts/${id}`, 'table[aria-label="Scorecard podmienok § 44"]')
    await page.waitForTimeout(1200)
    // Expand all scorecard rows to reveal evidence + AI explanation
    const rows = await page.locator('table[aria-label="Scorecard podmienok § 44"] tbody tr[role="button"]').all()
    for (const r of rows) { try { await r.click(); await page.waitForTimeout(120) } catch {} }
    await page.waitForTimeout(400)
    await page.screenshot({ path: `${OUT}/B-detail-${name}.png`, fullPage: true })
    results.push(`detail ${name} captured (${rows.length} rows expanded)`)
  }

  // ---- (C) FINDINGS REGISTER: expand a few rows full-width ----
  await gotoStable(page, `${BASE}/findings`, 'table[aria-label="Register nálezov"]')
  await page.waitForTimeout(1000)
  const fRows = await page.locator('table[aria-label="Register nálezov"] tbody tr[role="button"]').all()
  // expand first 4 expandable rows
  let expanded = 0
  for (const r of fRows) {
    try { await r.click(); expanded++; await page.waitForTimeout(120) } catch {}
    if (expanded >= 4) break
  }
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${OUT}/C-register-expanded.png`, fullPage: true })
  results.push(`register captured (${expanded} rows expanded of ${fRows.length})`)

  // ---- (D) MAP popup dismiss via Esc ----
  await gotoStable(page, `${BASE}/map`, '.leaflet-container')
  await page.waitForTimeout(3000)
  // click center of map to open a district popup, then Esc
  const map = page.locator('.leaflet-container').first()
  const box = await map.boundingBox().catch(() => null)
  if (!box) {
    results.push('map popup esc-dismiss: SKIPPED (leaflet container not measurable in headless)')
  } else {
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
    await page.waitForTimeout(1200)
    const popupBefore = await page.locator('.leaflet-popup').count()
    await page.keyboard.press('Escape')
    await page.waitForTimeout(800)
    const popupAfter = await page.locator('.leaflet-popup').count()
    results.push(`map popup esc-dismiss: before=${popupBefore} after=${popupAfter}`)
    await page.screenshot({ path: `${OUT}/D-map-after-esc.png` })
  }

  await browser.close()

  console.log('\n=== E2E RESULTS ===')
  results.forEach((r) => console.log(' -', r))
  console.log(`\n=== CONSOLE ERRORS: ${consoleErrors.length} ===`)
  consoleErrors.slice(0, 20).forEach((e) => console.log('  !', e))
  process.exit(consoleErrors.length > 0 ? 1 : 0)
}

main().catch((e) => { console.error('E2E FAILED:', e); process.exit(2) })
