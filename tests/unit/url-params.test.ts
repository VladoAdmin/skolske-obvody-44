import { describe, it, expect } from 'vitest'

describe('findings filter URL params', () => {
  function parseFilters(searchParamString: string): Record<string, string | null> {
    const params = new URLSearchParams(searchParamString)
    return {
      severity: params.get('severity'),
      status: params.get('status'),
      condition: params.get('condition'),
      page: params.get('page'),
    }
  }

  function buildFilters(
    filters: Record<string, string | undefined>
  ): string {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value)
    })
    return params.toString()
  }

  it('should parse empty params', () => {
    const filters = parseFilters('')
    expect(filters.severity).toBeNull()
    expect(filters.status).toBeNull()
    expect(filters.condition).toBeNull()
    expect(filters.page).toBeNull()
  })

  it('should parse single severity filter', () => {
    const filters = parseFilters('severity=critical')
    expect(filters.severity).toBe('critical')
    expect(filters.status).toBeNull()
  })

  it('should parse multiple filters', () => {
    const filters = parseFilters('severity=high&status=open&condition=S1&page=2')
    expect(filters.severity).toBe('high')
    expect(filters.status).toBe('open')
    expect(filters.condition).toBe('S1')
    expect(filters.page).toBe('2')
  })

  it('should build URL params from filter object', () => {
    const built = buildFilters({ severity: 'critical', status: 'open' })
    const filters = parseFilters(built)
    expect(filters.severity).toBe('critical')
    expect(filters.status).toBe('open')
  })

  it('should omit undefined filters', () => {
    const built = buildFilters({ severity: 'medium', status: undefined })
    expect(built).not.toContain('status')
    expect(built).toContain('severity=medium')
  })

  it('should support roundtrip: build → parse → build', () => {
    const original = { severity: 'low', condition: 'Pa', page: '3' }
    const built1 = buildFilters(original)
    const parsed = parseFilters(built1)
    const built2 = buildFilters(parsed as Record<string, string | undefined>)
    expect(built1).toBe(built2)
  })

  it('should handle page parameter correctly', () => {
    const filters = parseFilters('page=5')
    expect(filters.page).toBe('5')

    const built = buildFilters({ page: '10' })
    const updated = parseFilters(built)
    expect(updated.page).toBe('10')
  })
})
