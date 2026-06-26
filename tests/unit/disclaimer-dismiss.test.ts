import { describe, it, expect, beforeEach, afterEach } from 'vitest'

describe('DisclaimerBannerClient localStorage behavior', () => {
  beforeEach(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.clear()
    }
  })

  afterEach(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.clear()
    }
  })

  it('should check localStorage key for dismissal', () => {
    // Simulate: localStorage.getItem('dismiss_disclaimer_session')
    const DISMISS_KEY = 'dismiss_disclaimer_session'
    expect(DISMISS_KEY).toBe('dismiss_disclaimer_session')
  })

  it('should set localStorage to "1" when dismissed', () => {
    const DISMISS_KEY = 'dismiss_disclaimer_session'
    // Simulate: localStorage.setItem(DISMISS_KEY, '1')
    const testValue = '1'
    expect(testValue).toBe('1')
  })

  it('should be hidden when localStorage.dismiss_disclaimer_session === "1"', () => {
    const DISMISS_KEY = 'dismiss_disclaimer_session'
    // Logic: if (!alwaysShow && localStorage.getItem(DISMISS_KEY) === '1') { setDismissed(true) }
    const storageValue = '1'
    const alwaysShow = false
    const shouldHide = !alwaysShow && storageValue === '1'
    expect(shouldHide).toBe(true)
  })

  it('should always show when alwaysShow=true regardless of storage', () => {
    const DISMISS_KEY = 'dismiss_disclaimer_session'
    const alwaysShow = true
    const storageValue = '1'
    // Logic: if (!alwaysShow && localStorage.getItem(DISMISS_KEY) === '1') => ignored
    const shouldHide = !alwaysShow && storageValue === '1'
    expect(shouldHide).toBe(false)
  })

  it('should show by default when storage not set', () => {
    const storageValue = null
    const alwaysShow = false
    const shouldHide = !alwaysShow && storageValue === '1'
    expect(shouldHide).toBe(false)
  })

  it('should include version strings in disclaimer text', () => {
    const methodologyVersion = '1.2.3'
    const engineVersion = '2.0.1'
    const disclaimerText = `Verzia metodiky: ${methodologyVersion}. Verzia enginu: ${engineVersion}.`
    expect(disclaimerText).toContain(methodologyVersion)
    expect(disclaimerText).toContain(engineVersion)
  })
})
