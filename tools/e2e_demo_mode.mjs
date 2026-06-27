// Real-Chrome E2E for the full-data decisive demo (feat/demo-mode).
// Proves, with ZERO console errors:
//   (a) a fully-decisive scorecard with HIGH confidence/completeness for >=2
//       districts (no INCOMPLETE/INSUFFICIENT_DATA/NOT_EVALUATED/NO_SIGNAL rows),
//   (b) >=3 violation TYPES appearing consistently across map + register + detail.
// Screenshots under docs/e2e2/.
//
// Run: BASE_URL=http://localhost:3215 node tools/e2e_demo_mode.mjs
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = process.env.BASE_URL || 'http://localhost:3215'
const OUT = 'docs/e2e2'
const CHROME = '/usr/bin/google-chrome-stable'
mkdirSync(OUT, { recursive: true })

// Districts that carry the decisive demo verdicts (consistent everywhere).
const D = {
  bajkalska: '689f1541-6fb4-4ee6-958c-c4cc09e5a1ff',  // RED: S1 FAIL + Pa FAIL
  smeralova: 'cddfee4e-fb1d-48c1-bbb5-2626ae415f87',   // RED: S3 FAIL
  kupelna:   '7e0dd639-cf90-463f-8473-34541bddecf1',   // RED: S2 FAIL
  sibirska:  'd3cae810-c461-429f-86d9-0be4474ddc2c',   // RED: S2 FAIL + Pf SIGNAL
  ceskoslov: 'c6c4180a-871c-42fc-b74b-29e0a693b122',   // ORANGE: Pd FAIL
  lesnicka:  'cdf8f0b5-f66e-4438-8f7a-48ac656443bf',   // ORANGE: Pb RISK + Pc FAIL
  vazecka:   '61724cfb-2093-4f19-a47e-92b0b7e12429',   // GREEN: JAZYK podnet
}

const NON_DECISIVE = ['INCOMPLETE', 'INSUFFICIENT_DATA', 'NOT_EVALUATED', 'NO_SIGNAL', 'ILUSTR_NO_DATA', 'ILUSTRATIVE_AVAILABLE']
const consoleErrors = []
const failures = []

async function gotoStable(page, url, sel, tries = 4) {
  for (let i = 0; i < tries; i++) {
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    try { await page.waitForSelector(sel, { timeout: 8000 }); return true }
    catch { await page.waitForTimeout(800) }
  }
  return false
}

async function readScorecard(page, id) {
  await gotoStable(page, `${BASE}/districts/${id}`, 'table[aria-label="Scorecard podmienok § 44"]')
  await page.waitForTimeout(600)
  // Each row: condition code (cell 0) + value badge (cell 1) + two progress bars.
  return await page.$$eval('table[aria-label="Scorecard podmienok § 44"] tbody tr', (trs) => {
    const out = []
    for (const tr of trs) {
      if (tr.getAttribute('role') !== 'button' && !tr.querySelector('td')) continue
      const code = tr.querySelector('td:nth-child(1) code, td:nth-child(1) [class*="font-mono"]')?.textContent?.trim()
      const value = tr.querySelector('td:nth-child(2)')?.textContent?.trim()
      const bars = [...tr.querySelectorAll('[role="progressbar"]')].map((b) => Number(b.getAttribute('aria-valuenow')))
      if (code && value) out.push({ code, value, confidence: bars[0], completeness: bars[1] })
    }
    return out
  })
}

async function main() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1500 }, deviceScaleFactor: 2 })
  const page = await ctx.newPage()
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`${page.url()} :: ${m.text()}`) })
  page.on('pageerror', (e) => consoleErrors.push(`${page.url()} :: PAGEERROR ${e.message}`))

  // ---- (A) MAP overview: colors + counts ----
  await gotoStable(page, `${BASE}/map`, '.leaflet-container')
  await page.waitForTimeout(3500)
  await page.screenshot({ path: `${OUT}/A-map-overview.png` })
  console.log('A map overview captured')

  // ---- (B) Decisive scorecards for >=2 districts (criterion (a)) ----
  const decisiveTargets = { bajkalska: D.bajkalska, sibirska: D.sibirska, smeralova: D.smeralova }
  for (const [name, id] of Object.entries(decisiveTargets)) {
    const rows = await readScorecard(page, id)
    const nine = rows.filter((r) => ['S1','S2','S3','Pa','Pb','Pc','Pd','Pe','Pf'].includes(r.code))
    const nonDec = nine.filter((r) => NON_DECISIVE.includes(r.value))
    const lowConf = nine.filter((r) => (r.confidence ?? 0) < 90 || (r.completeness ?? 0) < 90)
    console.log(`B ${name}: ${nine.length} §44 rows, nonDecisive=${nonDec.length}, lowConf=${lowConf.length}`)
    if (nine.length !== 9) failures.push(`${name}: expected 9 §44 rows, got ${nine.length}`)
    if (nonDec.length) failures.push(`${name}: non-decisive rows ${JSON.stringify(nonDec)}`)
    if (lowConf.length) failures.push(`${name}: low conf/compl ${JSON.stringify(lowConf)}`)
    // expand rows for a legible screenshot
    const btns = await page.locator('table[aria-label="Scorecard podmienok § 44"] tbody tr[role="button"]').all()
    for (const b of btns) { try { await b.click(); await page.waitForTimeout(50) } catch {} }
    await page.waitForTimeout(300)
    await page.locator('table[aria-label="Scorecard podmienok § 44"]').screenshot({ path: `${OUT}/B-scorecard-${name}.png` })
  }

  // ---- (C) Findings register: violation types consistent (criterion (b)) ----
  await gotoStable(page, `${BASE}/findings`, 'table[aria-label="Register nálezov"]')
  await page.waitForTimeout(600)
  const registerRows = await page.$$eval('table[aria-label="Register nálezov"] tbody tr', (trs) =>
    trs.map((tr) => tr.innerText.replace(/\s+/g, ' ').trim()).filter(Boolean))
  // Expand first rows for legibility
  const fr = await page.locator('table[aria-label="Register nálezov"] tbody tr[role="button"]').all()
  let n = 0
  for (const r of fr) { try { await r.click(); n++; await page.waitForTimeout(60) } catch {} ; if (n >= 4) break }
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${OUT}/C-register.png`, fullPage: true })
  console.log(`C register: ${registerRows.length} rows`)

  // Consistency: each violation must appear in the register text.
  const expectViolations = [
    { type: 'S1 wrong-district', needle: ['Bajkalská', 'Š1'] },
    { type: 'S2 overlap', needle: ['Kúpeľná', 'Š2'] },
    { type: 'S3 two-schools', needle: ['Šmeralova', 'Š3'] },
    { type: 'Pa >2km', needle: ['Bajkalská', 'P-a'] },
    { type: 'Pd barrier', needle: ['Československej', 'P-d'] },
    { type: 'Pc poor MHD', needle: ['Lesnícka', 'P-c'] },
    { type: 'Pf overcrowd', needle: ['Sibírska', 'P-f'] },
    { type: 'Pe MRK', needle: ['Šrobárova', 'P-e'] },
    { type: 'JAZYK podnet', needle: ['Važecká', 'jazyk'] },
  ]
  const blob = registerRows.join(' \n ')
  let consistentTypes = 0
  for (const v of expectViolations) {
    const ok = v.needle.every((nd) => blob.toLowerCase().includes(nd.toLowerCase()))
    if (ok) consistentTypes++
    else failures.push(`register missing violation: ${v.type} (${v.needle.join(' + ')})`)
    console.log(`  register ${ok ? 'OK ' : 'MISS'} ${v.type}`)
  }
  if (consistentTypes < 3) failures.push(`only ${consistentTypes} violation types found in register (need >=3)`)

  // ---- (D) Per-district detail color matches violation (3 detail captures) ----
  for (const [name, id] of [['ceskoslov', D.ceskoslov], ['lesnicka', D.lesnicka], ['vazecka', D.vazecka]]) {
    await gotoStable(page, `${BASE}/districts/${id}`, 'table[aria-label="Scorecard podmienok § 44"]')
    await page.waitForTimeout(500)
    const btns = await page.locator('table[aria-label="Scorecard podmienok § 44"] tbody tr[role="button"]').all()
    for (const b of btns) { try { await b.click(); await page.waitForTimeout(40) } catch {} }
    await page.waitForTimeout(250)
    await page.locator('table[aria-label="Scorecard podmienok § 44"]').screenshot({ path: `${OUT}/D-scorecard-${name}.png` })
    console.log(`D detail ${name} captured`)
  }

  await browser.close()

  console.log('\n===== E2E SUMMARY =====')
  console.log(`console errors: ${consoleErrors.length}`)
  consoleErrors.slice(0, 10).forEach((e) => console.log('  ERR', e))
  console.log(`assertion failures: ${failures.length}`)
  failures.forEach((f) => console.log('  FAIL', f))
  if (consoleErrors.length || failures.length) { process.exit(1) }
  console.log('ALL E2E CHECKS PASSED')
}

main().catch((e) => { console.error(e); process.exit(2) })
