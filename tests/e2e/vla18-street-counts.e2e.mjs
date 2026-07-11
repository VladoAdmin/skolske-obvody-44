// VLA-18 gate — SummaryStrip real/mock/vzn_gap street counters.
//   Investigation (log/2026-07-11-vla-18-datagap-mock.md) found VLA-20 +
//   the existing VLA-14 vzn_gap classifier already give 100% street-level
//   coverage (377 VZN-matched + 23 vzn_gap = 400/400 register streets). No
//   mock district-assignment mechanism was needed; the remaining AC gap was
//   purely reporting.
//   [UAT-1] /map SummaryStrip shows "Ulice reálne" and "Ulice DEMO" counts
//           next to the existing "VZN medzera" counter.
//   [UAT-2] all three displayed numbers match a LIVE DB query — the engine
//           view (public.so_engine_metadata), not a hardcoded expectation.
// Plus the standing §44 gate: ZERO console errors.
import { mkdirSync } from 'fs'
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

const OUT = 'docs/proof'
mkdirSync(OUT, { recursive: true })

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
const ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

async function fetchRest(endpoint) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1${endpoint}`, {
    headers: { apikey: ANON_KEY, 'Accept-Profile': 'public' },
  })
  if (!res.ok) throw new Error(`REST ${endpoint} -> ${res.status}`)
  return res.json()
}

async function main() {
  if (!SUPABASE_URL || !ANON_KEY) {
    console.warn('SKIPPED: Supabase env not configured (NEXT_PUBLIC_SUPABASE_URL / _ANON_KEY)')
    return
  }

  // Live DB truth, queried the same way the app itself does (public REST,
  // anon key) — never hardcoded.
  const [meta] = await fetchRest('/so_engine_metadata?select=street_real_count,street_mock_count')
  const vznGapRows = await fetchRest('/so_street_coverage_gaps?select=category&category=eq.vzn_gap')
  const dbReal = meta.street_real_count
  const dbMock = meta.street_mock_count
  const dbVznGap = vznGapRows.length
  assert(dbReal > 0, `live DB street_real_count > 0, got ${dbReal}`)
  console.log(`DB truth: real=${dbReal} mock=${dbMock} vzn_gap=${dbVznGap}`)

  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'map')

  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)

  // [UAT-1] the three counters are present in the SummaryStrip.
  await page.waitForSelector('[data-testid="summary-street-real"]', { timeout: 20000 })
  await page.waitForSelector('[data-testid="summary-street-mock"]', { timeout: 20000 })
  await page.waitForSelector('[data-testid="summary-vzn-gaps"]', { timeout: 20000 })

  const stripReal = Number(await page.locator('[data-testid="summary-street-real"] dd').innerText())
  const stripMock = Number(await page.locator('[data-testid="summary-street-mock"] dd').innerText())
  const stripVznGap = Number(await page.locator('[data-testid="summary-vzn-gaps"] dd').innerText())

  // [UAT-2] rendered numbers match the live DB query exactly.
  assert(stripReal === dbReal, `summary strip "Ulice reálne" ${stripReal} === DB street_real_count ${dbReal}`)
  assert(stripMock === dbMock, `summary strip "Ulice DEMO" ${stripMock} === DB street_mock_count ${dbMock}`)
  assert(stripVznGap === dbVznGap, `summary strip "VZN medzera" ${stripVznGap} === DB vzn_gap count ${dbVznGap}`)

  await page.screenshot({ path: `${OUT}/vla18-street-counts.png` })
  console.log(`OK map: real=${stripReal} mock=${stripMock} vzn_gap=${stripVznGap} → vla18-street-counts.png`)

  await page.close()
  await browser.close()

  console.log('=== VLA-18 STREET COUNTS ===')
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: real/mock/vzn_gap counters render and match live DB query; zero console errors')
}

main().catch((e) => { console.error(e); process.exit(1) })
