// Shared helpers for the checkpoint-5 real-browser E2E scripts.
// Plain `playwright` (no @playwright/test in this environment) driving the
// system Chrome, matching the repo's existing tools/*.mjs convention.
// Named *.mjs (not *.spec.ts / *.test.ts) so vitest's default include never
// picks them up. Run directly: `BASE_URL=http://localhost:3219 node <script>`.
// The server must be BUILT AND STARTED with NEXT_PUBLIC_SO_SHOW_COMPLIANCE=1
// (step-2 display gate, lib/compliance/step1.ts) — without it the scorecard,
// detail findings and map legend are hidden and the proof-pack spec fails.
import { chromium } from 'playwright'

export const BASE = process.env.BASE_URL || 'http://localhost:3219'
export const CHROME = '/usr/bin/google-chrome-stable'

export async function launch() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true })
  const ctx = await browser.newContext({
    viewport: { width: 1366, height: 900 },
    deviceScaleFactor: 1.4,
  })
  return { browser, ctx }
}

/**
 * Track console errors + uncaught page errors per logical page key.
 * The §44 proof gate requires ZERO JS console errors on every page visited.
 * One listener per page object; `setKey` re-buckets errors when the same tab
 * navigates to the next page of the flow.
 */
export function makeErrorTracker() {
  const errors = {}
  const currentKey = new WeakMap()
  return {
    errors,
    attach(page, key) {
      errors[key] = errors[key] ?? []
      currentKey.set(page, key)
      page.on('console', (m) => {
        if (m.type() === 'error') errors[currentKey.get(page)].push(m.text())
      })
      page.on('pageerror', (e) => errors[currentKey.get(page)].push(String(e)))
    },
    setKey(page, key) {
      errors[key] = errors[key] ?? []
      currentKey.set(page, key)
    },
    report() {
      let total = 0
      for (const [k, v] of Object.entries(errors)) {
        total += v.length
        console.log(`console errors [${k}]: ${v.length}${v.length ? ' ' + JSON.stringify(v.slice(0, 5)) : ''}`)
      }
      return total
    },
  }
}

/**
 * Dismiss the first-load DEMO modal (components/disclaimer-banner.client.tsx)
 * with a REAL click on its "Rozumiem" button — the same flow a first-time
 * visitor performs. Persists via localStorage key demo_popup_seen_v1, so later
 * pages in the same context never show it again.
 */
export async function dismissDemoModal(page) {
  const dialog = page.locator('[role="dialog"]', { hasText: 'DEMO ukážka funkcionalít' })
  try {
    await dialog.waitFor({ state: 'visible', timeout: 5000 })
  } catch {
    return false // already dismissed in this context
  }
  await dialog.getByRole('button', { name: 'Rozumiem' }).click()
  await dialog.waitFor({ state: 'hidden', timeout: 5000 })
  return true
}

export function assert(cond, msg) {
  if (!cond) throw new Error(`ASSERT FAILED: ${msg}`)
}
