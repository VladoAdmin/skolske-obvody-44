// Checkpoint 5 — focused E2E for the findings-register scenario-type filter
// (checkpoint 4 feature, commit 42b1352):
//   A. register loads with rows and the count line
//   B. the "Typ scenára" select filters rows via a real UI interaction
//   C. switching the scenario re-filters (select drives ?scenario=)
//   D. a pagination-style URL (?scenario=…&page=1) keeps the filter applied
//   E. if pagination links render (dataset > PAGE_SIZE), every link carries
//      the active scenario param (pageHref builds from filterQuery)
// Gate: ZERO JS console errors on every register view visited.
//
// Known limit: the demo dataset has fewer findings than PAGE_SIZE (50), so
// pagination links do not render today — E covers the future case, D covers
// the "page param must not clobber the filter" contract now.
import { BASE, launch, makeErrorTracker, dismissDemoModal, assert } from './helpers.mjs'

// SCENARIO_TYPES_SK (app/findings/scenarios.ts) — SK label ↔ engine condition
// codes for the two scenarios exercised here.
const LONG_DISTANCE = { label: 'Veľká vzdialenosť', param: 'scenario=long_distance', codes: ['Pa', 'Pb'] }
const SEGREGATION = { label: 'Segregácia (Atlas MRK)', param: 'scenario=segregation_mrk', codes: ['Pe'] }

async function conditionCodes(page) {
  const codes = await page.locator('table code').allInnerTexts()
  return codes.map((c) => c.trim())
}

async function main() {
  const { browser, ctx } = await launch()
  const tracker = makeErrorTracker()
  const page = await ctx.newPage()
  tracker.attach(page, 'register-unfiltered')

  // A. Register loads.
  await page.goto(`${BASE}/findings`, { waitUntil: 'domcontentloaded' })
  await dismissDemoModal(page)
  await page.getByRole('heading', { name: 'Register nálezov' }).waitFor({ timeout: 20000 })
  await page.getByText(/Zobrazujem \d+–\d+ z \d+ nálezov/).waitFor({ timeout: 20000 })
  const allCodes = await conditionCodes(page)
  assert(allCodes.length > 0, 'unfiltered register shows rows')

  // B. Scenario select filters rows (real UI interaction).
  tracker.setKey(page, 'register-long-distance')
  await page.locator('#filter-scenario').click()
  await page.getByRole('option', { name: LONG_DISTANCE.label }).click()
  await page.waitForURL(`**${LONG_DISTANCE.param}**`, { timeout: 20000 })
  await page.getByText(/Zobrazujem \d+–\d+ z \d+ nálezov/).waitFor({ timeout: 20000 })
  const ldCodes = await conditionCodes(page)
  assert(ldCodes.length > 0, 'long-distance filter shows rows')
  assert(
    ldCodes.every((c) => LONG_DISTANCE.codes.includes(c)),
    `long-distance shows only Pa/Pb rows, got: ${ldCodes}`
  )
  assert(ldCodes.length < allCodes.length, 'filter narrowed the register')

  // C. Switching the scenario re-filters.
  tracker.setKey(page, 'register-segregation')
  await page.locator('#filter-scenario').click()
  await page.getByRole('option', { name: SEGREGATION.label }).click()
  await page.waitForURL(`**${SEGREGATION.param}**`, { timeout: 20000 })
  await page.getByText(/Zobrazujem \d+–\d+ z \d+ nálezov/).waitFor({ timeout: 20000 })
  const segCodes = await conditionCodes(page)
  assert(segCodes.length > 0, 'segregation filter shows rows')
  assert(
    segCodes.every((c) => SEGREGATION.codes.includes(c)),
    `segregation shows only Pe rows, got: ${segCodes}`
  )

  // D. Pagination-style URL keeps the filter: page param + scenario coexist.
  tracker.setKey(page, 'register-filter-with-page')
  await page.goto(`${BASE}/findings?${LONG_DISTANCE.param}&page=1`, { waitUntil: 'domcontentloaded' })
  await page.getByText(/Zobrazujem \d+–\d+ z \d+ nálezov/).waitFor({ timeout: 20000 })
  const trigger = await page.locator('#filter-scenario').innerText()
  assert(
    trigger.includes(LONG_DISTANCE.label),
    `scenario select still shows "${LONG_DISTANCE.label}" with page param, got: ${trigger}`
  )
  const pagedCodes = await conditionCodes(page)
  assert(
    pagedCodes.length > 0 && pagedCodes.every((c) => LONG_DISTANCE.codes.includes(c)),
    `rows stay filtered with page param, got: ${pagedCodes}`
  )

  // E. If pagination links render, each must carry the scenario filter.
  const pageLinks = await page.locator('a[href*="page="]').all()
  if (pageLinks.length === 0) {
    console.log('INFO: no pagination links (findings ≤ PAGE_SIZE) — E skipped by data, covered by D')
  } else {
    for (const link of pageLinks) {
      const href = await link.getAttribute('href')
      assert(
        href.includes(LONG_DISTANCE.param),
        `pagination link keeps the scenario filter: ${href}`
      )
    }
    console.log(`OK: ${pageLinks.length} pagination link(s) all carry ${LONG_DISTANCE.param}`)
  }

  await page.close()
  await browser.close()

  console.log('=== SCENARIO FILTER E2E ===')
  const total = tracker.report()
  if (total > 0) {
    console.error(`FAIL: ${total} console error(s) — §44 gate requires zero`)
    process.exit(1)
  }
  console.log('PASS: scenario filter flow green, zero console errors')
}

main().catch((e) => { console.error(e); process.exit(1) })
