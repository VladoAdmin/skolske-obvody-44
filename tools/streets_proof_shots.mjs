// Streets-pivot proof screenshots — districts rendered as coloured STREETS,
// no polygons, zero findings, detail page matching the main map.
// Run: BASE_URL=http://localhost:3219 node tools/streets_proof_shots.mjs
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = process.env.BASE_URL || 'http://localhost:3219'
const OUT = 'docs/proof'
const CHROME = '/usr/bin/google-chrome-stable'
mkdirSync(OUT, { recursive: true })

async function dismissPopup(page) {
  for (const name of ['Rozumiem', 'Zavrieť', 'OK']) {
    try {
      const btn = page.getByRole('button', { name })
      if (await btn.count()) { await btn.first().click({ timeout: 1500 }); await page.waitForTimeout(400) }
    } catch { /* none */ }
  }
}

async function gotoStable(page, url, sel) {
  for (let i = 0; i < 5; i++) {
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    try { await page.waitForSelector(sel, { timeout: 9000 }); await dismissPopup(page); return true }
    catch { await page.waitForTimeout(900) }
  }
  return false
}

const allErrors = {}
function track(page, key) {
  allErrors[key] = []
  page.on('console', (m) => { if (m.type() === 'error') allErrors[key].push(m.text()) })
  page.on('pageerror', (e) => allErrors[key].push(String(e)))
}

async function main() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, deviceScaleFactor: 1.4 })

  // 1) Main map — coloured street networks, no polygons.
  let page = await ctx.newPage()
  track(page, 'main-map')
  await gotoStable(page, `${BASE}/map`, '.leaflet-container')
  // Collapse the "Ako čítať mapu" details so it does not intercept map clicks.
  await page.evaluate(() => { document.querySelectorAll('details[open]').forEach((d) => d.removeAttribute('open')) })
  // Let the SVG street paths render (Leaflet draws them in the overlay pane).
  await page.waitForFunction(() => document.querySelectorAll('.leaflet-container path').length > 50, { timeout: 12000 }).catch(() => {})
  await page.waitForTimeout(1500)
  const pathCount = await page.evaluate(() => document.querySelectorAll('.leaflet-container path').length)
  await page.screenshot({ path: `${OUT}/streets-main-map.png` })

  // 2) Select a district via its list link's flyTo event is complex; instead
  // dispatch the in-app SELECT_DISTRICT event used by the findings panel, which
  // highlights that district's streets and dims the others — the same code path
  // as clicking a school pin.
  try {
    const did = await page.locator('a[href^="/districts/"]').first().getAttribute('href')
    const id = did.split('/').pop()
    await page.evaluate((districtId) => {
      window.dispatchEvent(new CustomEvent('so:select-district', { detail: { id: districtId } }))
    }, id)
    await page.waitForTimeout(1500)
    await page.screenshot({ path: `${OUT}/streets-main-map-selected.png` })
  } catch (e) { allErrors['main-map'].push('select: ' + e) }
  await page.close()

  // 3) Detail page — same street rendering, no polygons.
  page = await ctx.newPage()
  track(page, 'detail')
  // Pick the first district link from the obvody list.
  await gotoStable(page, `${BASE}/map`, 'a[href^="/districts/"]')
  const href = await page.locator('a[href^="/districts/"]').first().getAttribute('href')
  await page.close()

  page = await ctx.newPage()
  track(page, 'detail')
  await gotoStable(page, `${BASE}${href}`, '.leaflet-container')
  await page.waitForFunction(() => document.querySelectorAll('.leaflet-container path').length > 50, { timeout: 12000 }).catch(() => {})
  await page.waitForTimeout(2500)
  const detailPaths = await page.evaluate(() => document.querySelectorAll('.leaflet-container path').length)
  await page.screenshot({ path: `${OUT}/streets-detail-page.png` })
  await page.close()

  await browser.close()

  console.log('=== STREETS PIVOT PROOF ===')
  console.log('detail href:', href)
  console.log('main-map street paths:', pathCount)
  console.log('detail-page street paths:', detailPaths)
  for (const [k, v] of Object.entries(allErrors)) {
    console.log(`console errors [${k}]:`, v.length, v.slice(0, 5))
  }
  const total = Object.values(allErrors).reduce((a, b) => a + b.length, 0)
  console.log('TOTAL console errors:', total)
  process.exit(0)
}

main().catch((e) => { console.error(e); process.exit(1) })
