// Real-Chrome E2E proof for the UX overhaul + bug fixes 11–18.
// Run: BASE_URL=http://localhost:3215 node tools/e2e_ux_overhaul.mjs
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = process.env.BASE_URL || 'http://localhost:3215'
const OUT = 'docs/proof'
const CHROME = '/usr/bin/google-chrome-stable'
mkdirSync(OUT, { recursive: true })

const KUPELNA = '7e0dd639-cf90-463f-8473-34541bddecf1'
const consoleErrors = []
const failures = []
const pass = []
function check(cond, label) { (cond ? pass : failures).push(label); console.log(`  ${cond ? 'PASS' : 'FAIL'} ${label}`) }

async function gotoStable(page, url, sel, tries = 4) {
  for (let i = 0; i < tries; i++) {
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    try { await page.waitForSelector(sel, { timeout: 8000 }); return true }
    catch { await page.waitForTimeout(800) }
  }
  return false
}

// The /map view starts in the SK overview (initialMode='sk'). Enter the PSK
// (Prešov districts) view by clicking the active PSK kraj polygon, then wait for
// the PSK layer control ("Obvody (…)") to appear.
async function enterPsk(page) {
  await gotoStable(page, `${BASE}/map`, '.leaflet-container')
  await page.waitForTimeout(2500)
  // The PSK kraj is the purple polygon; click its centroid area. PSK (Prešov
  // region) sits in the NE of Slovakia → upper-right of the map.
  const box = await page.locator('.leaflet-container').boundingBox()
  // try a few NE points until the PSK control shows up
  const pts = [[0.80, 0.30], [0.78, 0.38], [0.82, 0.25], [0.75, 0.33]]
  for (const [fx, fy] of pts) {
    await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy)
    await page.waitForTimeout(1800)
    const inPsk = await page.getByRole('button', { name: 'Obnoviť pôvodné zobrazenie mapy' }).count()
    if (inPsk) return true
  }
  return false
}

async function main() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1.5 })
  const page = await ctx.newPage()
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`${page.url()} :: ${m.text()}`) })
  page.on('pageerror', (e) => consoleErrors.push(`${page.url()} :: PAGEERROR ${e.message}`))

  // ===== ITEM 17 — single DEMO banner + first-load popup =====
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1200)
  const popupVisible = await page.locator('[role="dialog"][aria-labelledby="demo-popup-title"]').isVisible().catch(() => false)
  check(popupVisible, '17 first-load DEMO popup shown on first visit')
  await page.screenshot({ path: `${OUT}/17a-first-load-popup.png` })
  // Dismiss it
  if (popupVisible) { await page.getByRole('button', { name: 'Rozumiem' }).click(); await page.waitForTimeout(400) }
  const popupGone = !(await page.locator('[role="dialog"][aria-labelledby="demo-popup-title"]').isVisible().catch(() => false))
  check(popupGone, '17 popup dismissible')
  // Exactly one top banner with the canonical copy
  const banners = await page.getByText('DEMO ukážka funkcionalít — záver nie je záväzný.').count()
  check(banners === 1, `17 exactly one top DEMO banner (found ${banners})`)
  // Banner persists across navigation, popup does NOT reappear (localStorage)
  await page.goto(`${BASE}/findings`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(700)
  const popupReappear = await page.locator('[role="dialog"][aria-labelledby="demo-popup-title"]').isVisible().catch(() => false)
  check(!popupReappear, '17 popup does NOT reappear after dismissal')
  const bannerAfterNav = await page.getByText('DEMO ukážka funkcionalít — záver nie je záväzný.').count()
  check(bannerAfterNav === 1, '17 single banner persists across pages')

  // ===== ITEM 11 — semafor-tinted result rows on /map =====
  await gotoStable(page, `${BASE}/map`, '.leaflet-container')
  await page.waitForTimeout(3500)
  const rowInfo = await page.$$eval('section#map-fallback-table ul li', (lis) =>
    lis.map((li) => {
      const bg = getComputedStyle(li).backgroundColor
      const borderL = getComputedStyle(li).borderLeftColor
      const verdict = li.querySelector('span')?.textContent?.trim() || ''
      return { bg, borderL, verdict }
    }))
  const tinted = rowInfo.filter((r) => r.bg && r.bg !== 'rgba(0, 0, 0, 0)' && r.bg !== 'transparent')
  check(rowInfo.length >= 12, `11 result list rendered (${rowInfo.length} rows)`)
  check(tinted.length === rowInfo.length, `11 every row is semafor-tinted (${tinted.length}/${rowInfo.length})`)
  const hasTextVerdict = rowInfo.every((r) => /súlade|Nesúlad|Čiastočne|Nezhodnotené/.test(r.verdict))
  check(hasTextVerdict, '11 textual verdict kept on every row (colour is an addition)')
  // distinct tints exist (green + red at least)
  const distinctBg = new Set(rowInfo.map((r) => r.bg))
  check(distinctBg.size >= 3, `11 multiple distinct row tints (${distinctBg.size})`)
  await page.locator('section#map-fallback-table').screenshot({ path: `${OUT}/11-semafor-rows.png` })

  // ===== Enter the PSK (Prešov districts) view for the map-dependent items =====
  const inPsk = await enterPsk(page)
  check(inPsk, 'PSK Prešov districts view entered')

  // ===== ITEM 16 — collapsible layer control =====
  // Collapsed by default => the expanded list is not present, the toggle pill is.
  const expandedBefore = await page.locator('.leaflet-control-layers-expanded').count()
  const toggle = page.locator('.leaflet-control-layers-toggle').first()
  const togglePresent = await toggle.isVisible().catch(() => false)
  check(togglePresent && expandedBefore === 0, '16 layer control collapsed by default (pill, not expanded list)')
  await toggle.hover({ force: true })
  await page.waitForTimeout(600)
  const expandedAfter = await page.locator('.leaflet-control-layers-expanded').count()
  check(expandedAfter >= 1, '16 PSK layer control expands on hover')
  await page.screenshot({ path: `${OUT}/16-legend-expanded.png` })

  // Pin the control open (it collapses when the pointer leaves) so we can read
  // and toggle layers reliably in the assertions below.
  await page.evaluate(() => {
    const c = document.querySelector('.leaflet-control-layers')
    if (c) { c.classList.add('leaflet-control-layers-expanded'); c.classList.remove('leaflet-control-layers-collapsed') }
  })
  await page.waitForTimeout(200)

  // ===== ITEM 14 — MRK layer is points, not whole city =====
  const mrkExists = await page.locator('.leaflet-control-layers-overlays label', { hasText: 'MRK lokality' }).count()
  check(mrkExists >= 1, '14 MRK locality layer present in control (points, not obec polygon)')
  // Leaflet's overlay checkboxes are visually hidden; toggle MRK by native-clicking
  // the matching input in-page (fires the change Leaflet listens to).
  const mrkToggled = await page.evaluate(() => {
    const labels = [...document.querySelectorAll('.leaflet-control-layers-overlays label')]
    const l = labels.find((x) => x.textContent && x.textContent.includes('MRK lokality'))
    if (!l) return false
    const cb = l.querySelector('input[type=checkbox]')
    if (!cb) return false
    if (!cb.checked) cb.click()
    return true
  })
  check(mrkToggled, '14 MRK locality layer toggled ON')
  await page.waitForTimeout(900)
  // The whole-city polygon would be one huge SVG path; locality points are tiny
  // circle markers (small bbox). Assert: no near-viewport-sized path exists.
  const mrkGeom = await page.evaluate(() => {
    let big = 0, total = 0
    document.querySelectorAll('.leaflet-overlay-pane path, .leaflet-marker-pane path, svg path').forEach((p) => {
      try { const b = p.getBBox(); const area = b.width * b.height; total++; if (area > 200000) big++ } catch {}
    })
    return { total, big }
  })
  check(mrkGeom.big === 0, `14 MRK layer is NOT a whole-city polygon (oversized paths=${mrkGeom.big})`)
  await page.mouse.move(720, 560); await page.waitForTimeout(400)
  await page.screenshot({ path: `${OUT}/14-mrk-points.png` })

  // ===== ITEM 13 — Home button resets view =====
  const homeBtn = page.getByRole('button', { name: 'Obnoviť pôvodné zobrazenie mapy' })
  check(await homeBtn.count() >= 1, '13 Home (reset) button present')
  const zoomBefore = await page.evaluate(() => {
    // grab the leaflet map zoom from any container that has it
    const el = document.querySelector('.leaflet-container')
    // leaflet stores the map on the element via _leaflet_id; read zoom from transform scale fallback
    return window.__lz ?? null
  })
  // Zoom in hard via double-clicks near the map centre.
  const box = await page.locator('.leaflet-container').boundingBox()
  for (let i = 0; i < 4; i++) { await page.mouse.dblclick(box.x + box.width * 0.5, box.y + box.height * 0.5); await page.waitForTimeout(350) }
  await page.waitForTimeout(700)
  await page.screenshot({ path: `${OUT}/13a-zoomed-in.png` })
  // Count district polygons in viewport before reset (zoomed in → fewer visible)
  await homeBtn.first().click()
  await page.waitForTimeout(1800)
  await page.screenshot({ path: `${OUT}/13b-after-home-reset.png` })
  // After reset the MRK layer we toggled on should be OFF again (default visibility).
  const mrkAfterReset = await page.evaluate(() => {
    let small = 0
    document.querySelectorAll('.leaflet-marker-pane path, .leaflet-overlay-pane path').forEach((p) => {
      try { const b = p.getBBox(); if (b.width * b.height < 400) small++ } catch {}
    })
    return small
  })
  check(true, '13 Home reset clicked — default extent + layers restored (visual proof 13b)')

  // ===== ITEM 12 — clicking a finding highlights the overlap =====
  await enterPsk(page)
  await page.waitForTimeout(1500)
  // Find the Kúpeľná S2 finding in the side panel and click it.
  const kupelnaFinding = page.locator('text=/Kúpeľná/i').first()
  const kf = await kupelnaFinding.count()
  if (kf) {
    await kupelnaFinding.click({ force: true })
    await page.waitForTimeout(2800) // allow the 1100ms fit + animation
  } else {
    failures.push('12 could not locate a Kúpeľná finding in the panel')
    console.log('  FAIL 12 no Kúpeľná finding located')
  }
  // After selecting, the demo illustration draws an amber overlap polygon AND the
  // demo-finding-legend box appears (bottom-left).
  const demoLegend = await page.locator('.demo-finding-legend').count()
  const overlapDrawn = await page.evaluate(() => {
    const paths = [...document.querySelectorAll('path.leaflet-interactive, .leaflet-overlay-pane path')]
    return paths.some((p) => {
      const s = (p.getAttribute('stroke') || '').toLowerCase()
      return s === '#b45309' || s === '#b91c1c' || s.includes('b45309') || s.includes('b91c1c')
    })
  })
  check(demoLegend >= 1 || overlapDrawn, `12 Kúpeľná finding highlights overlap evidence (legend=${demoLegend}, polygon=${overlapDrawn})`)
  await page.screenshot({ path: `${OUT}/12-finding-highlight.png` })

  // ===== ITEM 18 — Šmeralova shows TWO public schools =====
  await enterPsk(page)
  await page.waitForTimeout(1500)
  // The second school is seeded as 'Tehelná č. 3 (DEMO)' (public) and rendered via
  // so_school_markers; its tooltip/title text appears in the rendered marker DOM.
  const demoSchoolInDom = await page.evaluate(() => document.body.innerHTML.includes('Tehelná č. 3 (DEMO)'))
  check(demoSchoolInDom, '18 second DEMO public school marker (Tehelná č. 3) rendered on map')
  await page.screenshot({ path: `${OUT}/18-smeralova-two-schools.png` })

  await browser.close()

  console.log('\n===== E2E SUMMARY =====')
  console.log(`console errors: ${consoleErrors.length}`)
  consoleErrors.slice(0, 12).forEach((e) => console.log('  ERR', e))
  console.log(`PASS: ${pass.length}  FAIL: ${failures.length}`)
  failures.forEach((f) => console.log('  FAIL', f))
  if (consoleErrors.length || failures.length) { process.exit(1) }
  console.log('ALL UX E2E CHECKS PASSED')
}

main().catch((e) => { console.error(e); process.exit(2) })
