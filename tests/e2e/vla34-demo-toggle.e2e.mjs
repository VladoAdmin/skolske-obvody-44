// VLA-34 gate — global real-only / demo-mode toggle:
//   [UAT-1] a visible, working switch (role="switch", data-testid=
//           "demo-mode-toggle") is present in the app header on /map,
//           /findings and a district detail page (one global toggle, not
//           per-page — same DOM node, same state, across navigations).
//   [UAT-2] switching to real-only hides a known DEMO element (the seeded
//           fictional-railway barrier) and empties the findings surfaces
//           (every current finding in this dataset is is_demo=true);
//           switching back to demo mode brings them all back.
//   [UAT-3] the toggle survives navigation — sessionStorage persists it
//           across full page loads (page.goto), not just SPA nav.
// Plus the standing §44 gate: ZERO console errors on every page visited.
import { mkdirSync } from 'fs'
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

const OUT = 'docs/proof'
mkdirSync(OUT, { recursive: true })

// District with known DEMO findings (so_findings_panel.is_demo=true) —
// verified live via the REST API before writing this test.
const DEMO_FINDINGS_DISTRICT_ID = '689f1541-6fb4-4ee6-958c-c4cc09e5a1ff'

async function waitForBarrierCount(page, expected, timeout = 10000) {
  await page.waitForFunction(
    (n) => document.querySelectorAll('path.so-barrier').length === n,
    expected,
    { timeout }
  )
}

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map')

  // ── /map — default demo mode (must match current behaviour exactly) ────────
  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)

  const toggle = page.locator('[data-testid="demo-mode-toggle"]')
  assert(await toggle.count() === 1, '[UAT-1] demo-mode toggle present on /map')
  assert(await toggle.isVisible(), '[UAT-1] demo-mode toggle visible on /map')
  assert((await toggle.getAttribute('aria-checked')) === 'true', 'default mode is DEMO (aria-checked=true)')

  await waitForBarrierCount(page, 1)
  assert(
    (await page.locator('.leaflet-container').first().getAttribute('data-barriers')) === '1',
    'default demo mode: 1 DEMO barrier reported by the map'
  )

  const findingsSection = page.locator('section[aria-label="Nálezy"]')
  const findingsCountDemo = await findingsSection.locator('ul li button').count()
  assert(findingsCountDemo > 0, `demo mode: findings panel shows findings (got ${findingsCountDemo})`)

  await page.screenshot({ path: `${OUT}/vla34-map-demo-mode.png` })

  // ── flip to real-only ────────────────────────────────────────────────────
  await toggle.click()
  assert((await toggle.getAttribute('aria-checked')) === 'false', 'toggle reports real-only after click')
  assert(/[?&]demo=0(&|$)/.test(page.url()), '[UAT-3] URL reflects real-only mode (?demo=0)')

  // The map remounts (key change) to rebuild its layers from filtered data —
  // wait for the rebuilt container to report zero barriers.
  await waitForBarrierCount(page, 0)
  assert(
    (await page.locator('.leaflet-container').first().getAttribute('data-barriers')) === '0',
    '[UAT-2] real-only mode: 0 barriers reported by the map'
  )
  assert((await page.locator('path.so-barrier').count()) === 0, '[UAT-2] no DEMO barrier path drawn in real-only mode')

  // MRK localities are ALL is_demo=true in this dataset — the overlay entry
  // disappears from the layer control entirely (0-length array).
  const layersToggle = page.locator('.leaflet-control-layers-toggle').first()
  if (await layersToggle.count() > 0) await layersToggle.hover().catch(() => {})
  const layersTextRealOnly = await page.locator('.leaflet-control-layers').first().innerText().catch(() => '')
  assert(!/MRK lokality/i.test(layersTextRealOnly), '[UAT-2] MRK locality layer absent in real-only mode (all rows DEMO)')

  const findingsCountReal = await findingsSection.locator('ul li button').count()
  assert(findingsCountReal === 0, `[UAT-2] real-only mode: findings panel empty (all current findings are DEMO), got ${findingsCountReal}`)
  assert(
    (await findingsSection.locator('text=Žiadne nálezy pre vybrané filtre').count()) > 0,
    'findings panel shows the empty-state message in real-only mode'
  )

  await page.screenshot({ path: `${OUT}/vla34-map-real-only-mode.png` })
  console.log('OK /map: toggle hides DEMO barrier + MRK layer + findings in real-only mode')

  // ── flip back to demo — everything returns exactly as it was ───────────────
  await toggle.click()
  assert((await toggle.getAttribute('aria-checked')) === 'true', 'toggle reports demo mode again')
  assert(!/[?&]demo=0(&|$)/.test(page.url()), 'URL no longer carries demo=0')
  await waitForBarrierCount(page, 1)
  assert(
    (await page.locator('.leaflet-container').first().getAttribute('data-barriers')) === '1',
    '[UAT-2] toggling back to demo restores the barrier'
  )
  assert(
    (await findingsSection.locator('ul li button').count()) === findingsCountDemo,
    'toggling back to demo restores the original findings count'
  )
  console.log('OK /map: toggling back to demo restores original state exactly')

  // ── /findings register — toggle present + persists across a full nav ───────
  tracker.setKey(page, 'findings')
  // Flip to real-only BEFORE navigating, so the persistence itself is under test.
  await toggle.click()
  assert((await toggle.getAttribute('aria-checked')) === 'false', 'real-only set before navigating away')
  await page.goto(`${BASE}/findings`, { waitUntil: 'domcontentloaded' })
  const findingsToggle = page.locator('[data-testid="demo-mode-toggle"]')
  assert(await findingsToggle.count() === 1, '[UAT-1] demo-mode toggle present on /findings')
  assert(
    (await findingsToggle.getAttribute('aria-checked')) === 'false',
    '[UAT-3] real-only mode SURVIVED a full page navigation (sessionStorage)'
  )
  const findingsRowsReal = await page.locator('table[aria-label="Register nálezov"] tbody tr').count()
  assert(findingsRowsReal === 0, `[UAT-2] findings register empty in real-only mode (all rows DEMO), got ${findingsRowsReal}`)
  await page.screenshot({ path: `${OUT}/vla34-findings-real-only-mode.png` })

  await findingsToggle.click()
  assert((await findingsToggle.getAttribute('aria-checked')) === 'true', 'demo mode restored on /findings')
  await page.waitForSelector('table[aria-label="Register nálezov"] tbody tr', { timeout: 10000 })
  const findingsRowsDemo = await page.locator('table[aria-label="Register nálezov"] tbody tr').count()
  assert(findingsRowsDemo > 0, `demo mode: findings register shows rows again, got ${findingsRowsDemo}`)
  const demoBadges = await page.locator('table[aria-label="Register nálezov"] >> text=DEMO').count()
  assert(demoBadges > 0, 'demo mode: DEMO badges visible in the register')
  console.log('OK /findings: toggle present, persists across navigation, filters the register')

  // ── district detail — DEMO findings section disappears in real-only mode ──
  tracker.setKey(page, 'district-detail')
  await page.goto(`${BASE}/districts/${DEMO_FINDINGS_DISTRICT_ID}`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  const districtToggle = page.locator('[data-testid="demo-mode-toggle"]')
  assert(await districtToggle.count() === 1, '[UAT-1] demo-mode toggle present on district detail')
  assert((await districtToggle.getAttribute('aria-checked')) === 'true', 'demo mode still on (restored on /findings above)')
  assert(
    (await page.locator('h2#findings-heading').count()) === 1,
    'demo mode: district findings section ("Nálezy a dôkazy § 44") present'
  )

  await districtToggle.click()
  assert((await districtToggle.getAttribute('aria-checked')) === 'false', 'district detail toggled to real-only')
  await page.waitForFunction(
    () => document.getElementById('findings-heading') === null,
    { timeout: 10000 }
  )
  assert(
    (await page.locator('h2#findings-heading').count()) === 0,
    '[UAT-2] real-only mode: district findings section absent (all findings DEMO)'
  )
  await page.screenshot({ path: `${OUT}/vla34-district-detail-real-only-mode.png` })
  console.log('OK district detail: toggle present, DEMO findings section hidden in real-only mode')

  await page.close()
  await browser.close()

  console.log('=== VLA-34 DEMO-MODE TOGGLE ===')
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: all VLA-34 UATs green; zero console errors')
}

main().catch((e) => { console.error(e); process.exit(1) })
