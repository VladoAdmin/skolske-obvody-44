// Legible cropped captures of the scorecard tables for the deliverable.
import { chromium } from 'playwright'
const BASE = process.env.BASE_URL || 'http://localhost:3211'
const OUT = 'docs/e2e'
const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome-stable', headless: true })
const ctx = await b.newContext({ viewport: { width: 1280, height: 1400 }, deviceScaleFactor: 2 })
const p = await ctx.newPage()

async function cropScorecard(id, name) {
  await p.goto(`${BASE}/districts/${id}`, { waitUntil: 'networkidle' })
  await p.waitForSelector('table[aria-label="Scorecard podmienok § 44"]', { timeout: 15000 })
  const rows = await p.locator('table[aria-label="Scorecard podmienok § 44"] tbody tr[role="button"]').all()
  for (const r of rows) { try { await r.click(); await p.waitForTimeout(80) } catch {} }
  await p.waitForTimeout(400)
  const tbl = p.locator('table[aria-label="Scorecard podmienok § 44"]')
  await tbl.scrollIntoViewIfNeeded()
  await tbl.screenshot({ path: `${OUT}/legible-scorecard-${name}.png` })
  console.log(`scorecard ${name} cropped`)
}

await cropScorecard('cddfee4e-fb1d-48c1-bbb5-2626ae415f87', 'smeralova') // S3+Pa FAIL → RED
await cropScorecard('d3cae810-c461-429f-86d9-0be4474ddc2c', 'sibirska')   // Pf SIGNAL demo
await cropScorecard('61724cfb-2093-4f19-a47e-92b0b7e12429', 'vazecka')    // JAZYK demo

// Register close-up: viewport screenshot with first rows expanded.
await p.goto(`${BASE}/findings`, { waitUntil: 'networkidle' })
await p.waitForSelector('table[aria-label="Register nálezov"]', { timeout: 15000 })
const fr = await p.locator('table[aria-label="Register nálezov"] tbody tr[role="button"]').all()
let n = 0
for (const r of fr) { try { await r.click(); n++; await p.waitForTimeout(80) } catch {} ; if (n >= 3) break }
await p.waitForTimeout(300)
await p.locator('table[aria-label="Register nálezov"]').screenshot({ path: `${OUT}/legible-register.png` })
console.log('register cropped')

await b.close()
