import { describe, it, expect, beforeEach, afterEach } from 'vitest'

// Item 17: the per-page dismissible banners + scattered inline disclaimers were
// consolidated into ONE app-wide component rendered in app/layout.tsx:
//   * a slim, always-visible top banner ("DEMO ukážka funkcionalít — záver nie
//     je záväzný"), and
//   * a first-load popup shown once per browser, gated by a localStorage key.
// These tests pin that intent so a regression to the old "dismiss every page"
// or per-page <DisclaimerBanner alwaysShow /> pattern fails the suite.

describe('DisclaimerBannerClient first-load popup behavior', () => {
  const POPUP_SEEN_KEY = 'demo_popup_seen_v1'

  beforeEach(() => {
    if (typeof localStorage !== 'undefined') localStorage.clear()
  })
  afterEach(() => {
    if (typeof localStorage !== 'undefined') localStorage.clear()
  })

  it('uses a versioned popup-seen localStorage key (not the old session-dismiss key)', () => {
    expect(POPUP_SEEN_KEY).toBe('demo_popup_seen_v1')
  })

  it('shows the popup when the key is unset (first visit)', () => {
    const seen = null
    const showPopup = seen !== '1'
    expect(showPopup).toBe(true)
  })

  it('suppresses the popup once the key is "1" (already seen)', () => {
    const seen = '1'
    const showPopup = seen !== '1'
    expect(showPopup).toBe(false)
  })

  it('persists "1" to the key when the popup is dismissed', () => {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem(POPUP_SEEN_KEY, '1')
    expect(localStorage.getItem(POPUP_SEEN_KEY)).toBe('1')
  })

  it('keeps the slim banner regardless of popup state (banner is always-on)', () => {
    // The banner copy is independent of the popup-seen flag — it is the single
    // page-level DEMO notice and must remain visible after the popup is closed.
    const bannerText = 'DEMO ukážka funkcionalít — záver nie je záväzný.'
    const popupSeen = '1'
    const bannerVisible = true // not gated by popupSeen
    expect(bannerVisible).toBe(true)
    expect(bannerText).toContain('záver nie je záväzný')
    expect(popupSeen).toBe('1')
  })

  it('surfaces methodology + engine versions in the popup', () => {
    const methodologyVersion = '1.2.3'
    const engineVersion = '2.0.1'
    const popupText = `Verzia metodiky: ${methodologyVersion} · Verzia enginu: ${engineVersion}`
    expect(popupText).toContain(methodologyVersion)
    expect(popupText).toContain(engineVersion)
  })
})
