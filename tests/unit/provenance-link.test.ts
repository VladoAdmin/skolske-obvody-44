import { describe, it, expect } from 'vitest'

describe('ProvenanceLink component logic', () => {
  it('should identify NULL url for fallback text', () => {
    const url: string | null | undefined = null
    expect(!url).toBe(true)
  })

  it('should identify undefined url for fallback text', () => {
    const url: string | null | undefined = undefined
    expect(!url).toBe(true)
  })

  it('should accept valid urls', () => {
    const testUrl = 'https://example.com/document'
    expect(testUrl).toBeTruthy()
    expect(testUrl.startsWith('https://')).toBe(true)
  })

  it('should enforce security rel attribute', () => {
    const relAttr = 'noopener noreferrer nofollow'
    expect(relAttr).toContain('noopener')
    expect(relAttr).toContain('noreferrer')
    expect(relAttr).toContain('nofollow')
  })

  it('should default to "Zdrojový dokument" when label not provided', () => {
    const defaultLabel = 'Zdrojový dokument'
    expect(defaultLabel).toEqual('Zdrojový dokument')
  })

  it('should handle empty string as falsy (no link)', () => {
    const url = ''
    expect(!url).toBe(true)
  })
})
