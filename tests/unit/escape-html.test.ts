import { describe, it, expect } from 'vitest'
import { escapeHtml } from '@/lib/compliance/school-popup'

// VLA-17 PR #4 review (GPT-5.5, 2026-07-10): district/route/place labels are
// DB-sourced strings spliced into Leaflet popup/tooltip HTML strings, which
// Leaflet renders via innerHTML. Any label containing HTML-special
// characters would render as markup, not text, if unescaped — this guards
// the fix (escapeHtml on districtName / origin_label / transit_line in
// components/region-map.client.tsx).
describe('escapeHtml', () => {
  it('neutralizes a script tag so it cannot execute as markup', () => {
    const out = escapeHtml('<script>alert(1)</script>')
    expect(out).not.toContain('<script>')
    expect(out).toBe('&lt;script&gt;alert(1)&lt;/script&gt;')
  })

  it('escapes attribute-breakout characters (quotes) used in the popup HTML string', () => {
    const out = escapeHtml('Hlavná" onmouseover="alert(1)')
    expect(out).not.toContain('"')
    expect(out).toContain('&quot;')
  })

  it('leaves plain district/street/transit-line text unchanged in content', () => {
    expect(escapeHtml('Sídlisko Sekčov')).toBe('Sídlisko Sekčov')
    expect(escapeHtml('Linka 12')).toBe('Linka 12')
  })
})
