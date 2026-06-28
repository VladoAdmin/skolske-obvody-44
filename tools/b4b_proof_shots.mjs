// Batch-4b proof screenshots — address/segregation dots INSIDE their districts.
// Run: BASE_URL=http://localhost:3215 node tools/b4b_proof_shots.mjs
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = process.env.BASE_URL || 'http://localhost:3215'
const OUT = 'docs/proof'
const CHROME = '/usr/bin/google-chrome-stable'
mkdirSync(OUT, { recursive: true })

// RED district whose Pa illustration draws a >2km line to a contained address.
const BAJKALSKA = '689f1541-6fb4-4ee6-958c-c4cc09e5a1ff'
// Pe SIGNAL (MRK segregation locality) district.
const SROBAROVA = '9f1e3d72-5246-4414-9340-bccc2d6036d0'
// GREEN district with 300+ contained address dots.
const PROSTEJOVSKA = '6f4bee27-013c-4937-8dd7-73f3a28a7118'

async function stable(page, url, sel, tries = 5) {
  for (let i = 0; i < tries; i++) {
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    try { await page.waitForSelector(sel, { timeout: 9000 }); await dismissPopup(page); return true }
    catch { await page.waitForTimeout(900) }
  }
  return false
}

// The first-load DEMO modal overlays the map; click "Rozumiem" to dismiss it so
// the map and its dots are visible and clickable in screenshots.
async function dismissPopup(page) {
  const btn = page.getByRole('button', { name: 'Rozumiem' })
  try {
    if (await btn.count()) { await btn.first().click({ timeout: 2000 }); await page.waitForTimeout(500) }
  } catch { /* already dismissed */ }
}

async function main() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, deviceScaleFactor: 1.4 })
  const page = await ctx.newPage()
  const errs = []
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()) })
  page.on('pageerror', (e) => errs.push('PAGEERROR ' + e.message))

  // (1) Full region map framed on Prešov: all 12 single-polygon districts.
  await stable(page, `${BASE}/map`, '.leaflet-container')
  await page.waitForTimeout(2800)
  await page.screenshot({ path: `${OUT}/b4b-map-presov.png` })
  console.log('saved b4b-map-presov.png')

  // (1b) Enable the address-points layer and zoom in ONE step so the house dots
  // render INSIDE their districts while the district mosaic is still readable.
  const ctrl = page.locator('.leaflet-control-layers').first()
  await ctrl.hover().catch(() => {})
  await page.waitForTimeout(600)
  const addrToggle = page.getByText(/Adresné body obvodov/).first()
  if (await addrToggle.count()) {
    const cb = addrToggle.locator('xpath=preceding-sibling::input[1]')
    if (await cb.count()) { await cb.first().check({ force: true }).catch(() => {}) }
    else {
      const box = await addrToggle.boundingBox()
      if (box) { await page.mouse.click(box.x - 10, box.y + box.height / 2) }
    }
  }
  await page.locator('.leaflet-control-zoom-in').click().catch(() => {})
  await page.waitForTimeout(700)
  await page.locator('.leaflet-control-zoom-in').click().catch(() => {})
  await page.waitForTimeout(2500)
  await page.screenshot({ path: `${OUT}/b4b-map-address-dots.png` })
  console.log('saved b4b-map-address-dots.png')

  // (2) Bajkalská detail — contained addresses + Pa >2km line to a real inside address.
  await stable(page, `${BASE}/districts/${BAJKALSKA}`, '.leaflet-container')
  await page.waitForTimeout(3000)
  await page.screenshot({ path: `${OUT}/b4b-detail-bajkalska.png` })
  console.log('saved b4b-detail-bajkalska.png')

  // (3) Šrobárova detail — Pe MRK segregation locality point inside its district.
  await stable(page, `${BASE}/districts/${SROBAROVA}`, '.leaflet-container')
  await page.waitForTimeout(3000)
  // Enable the MRK locality layer (off by default) so the segregation point shows.
  const dctrl = page.locator('.leaflet-control-layers').first()
  await dctrl.hover().catch(() => {})
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${OUT}/b4b-detail-srobarova-pe.png` })
  console.log('saved b4b-detail-srobarova-pe.png')

  // (4) Prostějovská detail — densely populated GREEN district, all dots contained.
  await stable(page, `${BASE}/districts/${PROSTEJOVSKA}`, '.leaflet-container')
  await page.waitForTimeout(3000)
  await page.screenshot({ path: `${OUT}/b4b-detail-prostejovska.png` })
  console.log('saved b4b-detail-prostejovska.png')

  await browser.close()
  console.log('console errors:', errs.length, errs.slice(0, 5))
}

main().catch((e) => { console.error(e); process.exit(1) })
