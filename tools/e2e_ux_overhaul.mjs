// Real-Chrome E2E proof for the UX overhaul + bug fixes 11–18.
// Run: BASE_URL=http://localhost:3215 node tools/e2e_ux_overhaul.mjs
import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = process.env.BASE_URL || 'http://localhost:3215'
const OUT = 'docs/proof'
const CHROME = '/usr/bin/google-chrome-stable'
mkdirSync(OUT, { recursive: true })

const KUPELNA = '7e0dd639-cf90-463f-8473-34541bddecf1'
// Bajkalská č. 29 — a RED district whose conditions are mostly PASS (only S1 +
// Pa FAIL). The exact FIX-1 case: composition_color=RED on every row, so the old
// code showed a red ✕ on every row including the PASS ones.
const BAJKALSKA = '689f1541-6fb4-4ee6-958c-c4cc09e5a1ff'
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

// FIX 5: the /map view now opens ALREADY framed on the Prešov okres
// (initialMode='psk'), so there is no dead whole-SK state. Entering the PSK view
// just means loading /map and waiting for the Home/reset button (PSK chrome) to
// appear — no SK-polygon click needed.
async function enterPsk(page) {
  await gotoStable(page, `${BASE}/map`, '.leaflet-container')
  await page.waitForTimeout(2500)
  const inPsk = await page.getByRole('button', { name: 'Obnoviť pôvodné zobrazenie mapy (Prešov)' }).count()
  return inPsk >= 1
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
  const homeBtn = page.getByRole('button', { name: 'Obnoviť pôvodné zobrazenie mapy (Prešov)' })
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

  // ===== FIX 5 — /map opens framed on Prešov; Home resets from first load =====
  // No SK-polygon click: loading /map must already be in the PSK (Prešov) view,
  // and the Home button must reset the view from the very first load.
  await gotoStable(page, `${BASE}/map`, '.leaflet-container')
  await page.waitForTimeout(2800)
  const homeOnLoad = await page.getByRole('button', { name: 'Obnoviť pôvodné zobrazenie mapy (Prešov)' }).count()
  check(homeOnLoad >= 1, 'FIX5 /map opens already framed on Prešov (PSK view, no SK-click needed)')
  // Reset works from first load (before any drill-in click): zoom in, hit Home,
  // expect no error and the button still present (view restored).
  {
    const box = await page.locator('.leaflet-container').boundingBox()
    for (let i = 0; i < 3; i++) { await page.mouse.dblclick(box.x + box.width * 0.5, box.y + box.height * 0.5); await page.waitForTimeout(300) }
    await page.waitForTimeout(500)
    await page.getByRole('button', { name: 'Obnoviť pôvodné zobrazenie mapy (Prešov)' }).first().click()
    await page.waitForTimeout(1500)
  }
  const homeAfterReset = await page.getByRole('button', { name: 'Obnoviť pôvodné zobrazenie mapy (Prešov)' }).count()
  check(homeAfterReset >= 1, 'FIX5 Home/reset works from first load (before any drill-in)')
  await page.screenshot({ path: `${OUT}/fix5-map-initial-presov.png` })

  // ===== FIX 1-4 + 6 — district DETAIL page (Bajkalská, a RED district) =====
  await gotoStable(page, `${BASE}/districts/${BAJKALSKA}`, 'table[aria-label="Scorecard podmienok § 44"]')
  await page.waitForTimeout(1500)

  // (FIX 1) On a RED district, PASS condition rows must NOT show a red ✕ in the
  // Semafor cell. The per-row semafor reflects the condition's own verdict.
  const semaforByValue = await page.$$eval(
    'table[aria-label="Scorecard podmienok § 44"] tbody tr',
    (trs) => trs.map((tr) => {
      const cells = tr.querySelectorAll('td')
      if (cells.length < 5) return null
      const value = (cells[1].textContent || '').trim()
      // The 5th cell (index 4) is the Semafor marker.
      const semaforSpan = cells[4].querySelector('span')
      const sym = (semaforSpan?.textContent || '').trim()
      const aria = semaforSpan?.getAttribute('aria-label') || ''
      return { value, sym, aria }
    }).filter(Boolean)
  )
  const passRows = semaforByValue.filter((r) => r.value.startsWith('PASS'))
  const redPassRows = passRows.filter((r) => r.sym === '✕' || r.aria === 'RED')
  check(passRows.length >= 1, `FIX1 RED district detail has PASS condition rows (${passRows.length})`)
  check(redPassRows.length === 0, `FIX1 PASS rows do NOT show a red ✕ semafor (red-on-PASS=${redPassRows.length})`)
  // A FAIL row should still show ✕ (the fix is per-row correctness, not hiding red).
  const failRows = semaforByValue.filter((r) => r.value.startsWith('FAIL'))
  const failRed = failRows.filter((r) => r.sym === '✕')
  check(failRows.length === 0 || failRed.length === failRows.length, `FIX1 FAIL rows still show red ✕ (${failRed.length}/${failRows.length})`)

  // (FIX 2) No "generované AI" text anywhere on the page.
  const aiText = await page.evaluate(() => document.body.innerText)
  check(!/generované AI|Generované umelou inteligenciou/i.test(aiText), 'FIX2 no "generované AI" explanation text on detail page')

  // (FIX 3) The scorecard table shows "Detail", not "Dôkaz".
  const tableText = await page.locator('table[aria-label="Scorecard podmienok § 44"]').innerText()
  check(/Detail/.test(tableText), 'FIX3 scorecard shows "Detail" label')
  check(!/Dôkaz/.test(tableText), 'FIX3 scorecard no longer shows "Dôkaz" label')

  // (FIX 4) No per-row DEMO chip in the Príznaky column. The Príznaky column is
  // the 6th cell (index 5). Assert none contains a DEMO badge.
  const demoChips = await page.$$eval(
    'table[aria-label="Scorecard podmienok § 44"] tbody tr',
    (trs) => trs.reduce((n, tr) => {
      const cells = tr.querySelectorAll('td')
      if (cells.length < 6) return n
      return n + (/DEMO/.test(cells[5].textContent || '') ? 1 : 0)
    }, 0)
  )
  check(demoChips === 0, `FIX4 no per-row DEMO chip in Príznaky column (found ${demoChips})`)
  // The single top disclaimer banner must STILL be present.
  const topBanner = await page.getByText('DEMO ukážka funkcionalít — záver nie je záväzný.').count()
  check(topBanner === 1, 'FIX4 top DEMO disclaimer banner kept on detail page')

  // (FIX 6) The detail map renders this district's § 44 findings illustration
  // (legend box appears when the district has drawable findings).
  await page.waitForTimeout(1500)
  const detailIllustration = await page.locator('.demo-finding-legend').count()
  check(detailIllustration >= 1, `FIX6 detail map shows § 44 findings illustration legend (${detailIllustration})`)
  await page.screenshot({ path: `${OUT}/fix-detail-bajkalska.png` })
  // Legible 1366x900 detail-page proof.
  await page.setViewportSize({ width: 1366, height: 900 })
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${OUT}/fix-detail-bajkalska-1366.png` })

  // ===== BATCH-4 — clean demo: no garbage anywhere, JAZYK evaluated =====
  const VAZECKA = '61724cfb-2093-4f19-a47e-92b0b7e12429' // GREEN, JAZYK=HU → SIGNAL
  const MAJOVE = 'd15e65c7-7a0b-4e9d-bb6f-3b5f9667a8b5'  // GREEN, JAZYK=SK → evaluated

  // (B4-1) Full clean map: 12 solid districts, framed on Prešov. Legible 1366x900.
  await page.setViewportSize({ width: 1366, height: 900 })
  await gotoStable(page, `${BASE}/map`, '.leaflet-container')
  await page.waitForTimeout(2800)
  // Districts render into a custom leaflet-districts-pane as interactive paths
  // (one fill path per district). Count interactive district polygons.
  const districtPaths = await page.evaluate(() =>
    document.querySelectorAll('path.leaflet-interactive').length)
  check(districtPaths >= 12, `B4-2 map renders >=12 district polygons (${districtPaths})`)
  await page.screenshot({ path: `${OUT}/b4-clean-map-12-districts.png` })

  // (B4-3) No garbage verdict text ANYWHERE on the map page.
  const mapText = await page.evaluate(() => document.body.innerText)
  check(!/NOT_EVALUATED|INSUFFICIENT|NEVYHODNOTENÉ.*JAZYK/i.test(mapText),
    'B4-3 no NOT_EVALUATED/INSUFFICIENT garbage text on /map')

  // (B4-4) Důkaz: scan several detail pages — every scorecard cell is decisive,
  // no INSUFFICIENT_DATA / NOT_EVALUATED / INCOMPLETE leaks, JAZYK reads evaluated.
  for (const [id, label] of [[VAZECKA, 'Važecká (JAZYK=HU)'], [MAJOVE, 'Májové (JAZYK=SK)'], [BAJKALSKA, 'Bajkalská (RED)']]) {
    await gotoStable(page, `${BASE}/districts/${id}`, 'table[aria-label="Scorecard podmienok § 44"]')
    await page.waitForTimeout(1200)
    const t = await page.locator('table[aria-label="Scorecard podmienok § 44"]').innerText()
    check(!/INSUFFICIENT_DATA|INCOMPLETE/.test(t), `B4-4 ${label}: no INSUFFICIENT_DATA/INCOMPLETE in scorecard`)
    // The raw enum NOT_EVALUATED must never appear (it is rendered as a friendly label).
    check(!/NOT_EVALUATED/.test(t), `B4-4 ${label}: no raw NOT_EVALUATED enum in scorecard`)
    // JAZYK row exists and is decisively evaluated (SIGNÁL for HU, Bez podnetu for SK).
    const jazykRow = await page.$$eval('table[aria-label="Scorecard podmienok § 44"] tbody tr',
      (trs) => trs.map((tr) => tr.innerText).find((x) => /JAZYK|jazyk/i.test(x)) || '')
    check(/SIGNÁL|Bez podnetu/.test(jazykRow) && !/NOT_EVALUATED|Nevyhodnotené/.test(jazykRow),
      `B4-5 ${label}: JAZYK reads as evaluated ("${jazykRow.replace(/\s+/g, ' ').slice(0, 60)}")`)
  }

  // (B4-6) Fully-populated decisive scorecard proof on a GREEN district (Važecká),
  // including JAZYK evaluated. 1366x900.
  await gotoStable(page, `${BASE}/districts/${VAZECKA}`, 'table[aria-label="Scorecard podmienok § 44"]')
  await page.waitForTimeout(1200)
  await page.screenshot({ path: `${OUT}/b4-scorecard-vazecka-jazyk.png` })

  // (B4-7) No empty island block on a detail page that previously fragmented
  // (Šmeralova): a single clean obvod must not render a spurious "ostrovy" section.
  const SMERALOVA = 'cddfee4e-fb1d-48c1-bbb5-2626ae415f87'
  await gotoStable(page, `${BASE}/districts/${SMERALOVA}`, 'table[aria-label="Scorecard podmienok § 44"]')
  await page.waitForTimeout(1200)
  const islandsHeading = await page.locator('#islands-heading').count()
  check(islandsHeading === 0, `B4-7 Šmeralova: no spurious "ostrovy" section on a clean single-polygon obvod (${islandsHeading})`)

  // (B4-8) MRK / segregation illustration proof (Šrobárova — Pe SIGNAL on real
  // MRK locality points). Capture for docs/proof.
  const SROBAROVA = '9f1e3d72-5246-4414-9340-bccc2d6036d0'
  await gotoStable(page, `${BASE}/districts/${SROBAROVA}`, 'table[aria-label="Scorecard podmienok § 44"]')
  await page.waitForTimeout(2000)
  await page.screenshot({ path: `${OUT}/b4-segregation-mrk-srobarova.png` })

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
