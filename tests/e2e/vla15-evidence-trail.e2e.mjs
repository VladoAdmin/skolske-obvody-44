// VLA-15 gate — evidence trail for street-level verdicts (client feedback
// 2026-07-06: a verdict without visible reasoning must not be presented as
// an assertion):
//   [UAT-1] /findings: the Bajkalská S1 finding (demo scenario built on the
//           real VZN split of Šmeralova between ZŠ Bajkalská 27–29 and
//           ZŠ Šmeralova 1–23) expands into "Ako sme na to prišli" with all
//           four evidence elements: VZN citation, Register adries state,
//           geometry evidence, Slovak conclusion.
//   [UAT-2] deep link /findings#f-<id> auto-expands that finding's trail.
//   [UAT-3] no finding without provenance: EVERY register row expands and
//           shows the Zdroj/Metóda line (source + method of the verdict).
//   [UAT-4] /map: selecting the finding shows the district evidence legend
//           with the short conclusion + a link into the register entry.
// Plus the standing §44 gate: ZERO console errors on every page visited.
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'findings')

  // ── [UAT-1] /findings — Bajkalská S1 trail ────────────────────────────────
  await page.goto(`${BASE}/findings`, { waitUntil: 'domcontentloaded' })
  await dismissDemoModal(page)
  await page.waitForSelector('table[aria-label="Register nálezov"]', { timeout: 20000 })

  const s1Row = page.locator('table[aria-label="Register nálezov"] tr[id^="f-"]', {
    hasText: 'Bajkalská č. 29',
  }).filter({ hasText: 'Š1' }).first()
  assert(await s1Row.count() === 1, 'Bajkalská S1 finding row present in the register')
  const findingId = (await s1Row.getAttribute('id')).slice(2)

  await s1Row.click()
  const trail = page.locator('[data-testid="evidence-trail"]:visible').first()
  await trail.waitFor({ state: 'visible', timeout: 5000 })
  const trailText = await trail.innerText()
  assert(trailText.includes('Ako sme na to prišli'), 'trail heading "Ako sme na to prišli" shown')
  for (const label of ['VZN (uličný zoznam)', 'Register adries', 'Geometria obvodov', 'Záver']) {
    assert(trailText.includes(label), `trail element "${label}" shown`)
  }
  // The VZN citation must quote the real street split of the demo scenario.
  assert(trailText.includes('Šmeralova'), 'VZN citation cites the Šmeralova split')
  assert(trailText.includes('Zdroj'), 'provenance source (Zdroj) shown')
  assert(trailText.includes('Metóda'), 'provenance method (Metóda) shown')

  // ── [UAT-2] deep link auto-expands the trail ─────────────────────────────
  tracker.setKey(page, 'findings-deeplink')
  await page.goto(`${BASE}/findings#f${'-'}${findingId}`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('table[aria-label="Register nálezov"]', { timeout: 20000 })
  const deepTrail = page.locator('[data-testid="evidence-trail"]:visible').first()
  await deepTrail.waitFor({ state: 'visible', timeout: 5000 })
  assert(
    (await deepTrail.innerText()).includes('Ako sme na to prišli'),
    'deep link #f-<id> auto-expands the evidence trail'
  )

  // ── [UAT-3] every finding carries provenance (source + method) ───────────
  tracker.setKey(page, 'findings-provenance')
  await page.goto(`${BASE}/findings`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('table[aria-label="Register nálezov"]', { timeout: 20000 })
  const rows = page.locator('table[aria-label="Register nálezov"] tbody tr[id^="f-"]')
  const rowCount = await rows.count()
  assert(rowCount > 0, `register has findings (got ${rowCount})`)
  for (let i = 0; i < rowCount; i++) {
    const row = rows.nth(i)
    await row.click()
    const rowTrail = page.locator('[data-testid="evidence-trail"]:visible').first()
    await rowTrail.waitFor({ state: 'visible', timeout: 5000 })
    const text = await rowTrail.innerText()
    assert(
      text.includes('Zdroj') && text.includes('Metóda'),
      `finding row ${i + 1}/${rowCount} shows Zdroj + Metóda`
    )
    await row.click() // collapse before the next row
  }
  console.log(`[UAT-3] all ${rowCount} findings show source + method`)

  // ── [UAT-4] /map — legend with short trail + register link ───────────────
  tracker.setKey(page, 'map')
  await page.goto(`${BASE}/map`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.leaflet-container', { timeout: 20000 })
  await dismissDemoModal(page)

  // Select the Bajkalská S1 finding in the findings section → fly-to +
  // district selection → evidence legend renders on the map.
  const findingsSection = page.locator('section[aria-label="Nálezy"]')
  const panelItem = findingsSection.locator('button', { hasText: 'Bajkalská č. 29' })
    .filter({ hasText: 'Š1' }).first()
  assert(await panelItem.count() === 1, 'Bajkalská S1 item present in the map findings panel')
  await panelItem.click()

  const legend = page.locator('.district-evidence-legend')
  await legend.waitFor({ state: 'visible', timeout: 10000 })
  const legendText = await legend.innerText()
  assert(legendText.includes('Záver'), 'map legend shows the short conclusion (Záver)')
  const registerLink = legend.locator(`a[href="/findings#f-${findingId}"]`)
  assert(await registerLink.count() === 1, 'map legend links to the register entry /findings#f-<id>')
  assert(
    (await registerLink.innerText()).includes('Detail v registri nálezov'),
    'register link labelled "Detail v registri nálezov"'
  )
  // Panel item (selected) also shows the conclusion + register link.
  const panelText = await panelItem.innerText()
  assert(panelText.includes('Záver'), 'panel selected item shows the conclusion')

  // ── standing gate: zero console errors ───────────────────────────────────
  const totalErrors = tracker.report()
  assert(totalErrors === 0, `zero console errors, got ${totalErrors}`)

  await browser.close()
  console.log('\nVLA-15 E2E: ALL ASSERTIONS PASSED')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
