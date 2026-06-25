import { describe, it, expect, beforeAll } from 'vitest'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
const ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

const headers = {
  'apikey': ANON_KEY,
  'Accept-Profile': 'public',
  'Content-Type': 'application/json',
}

async function fetchRest(endpoint: string) {
  if (!SUPABASE_URL) return { status: 0, data: null, ok: false }
  const url = `${SUPABASE_URL}/rest/v1${endpoint}`
  try {
    const response = await fetch(url, { headers })
    return {
      status: response.status,
      data: response.status === 200 ? await response.json() : null,
      ok: response.ok,
    }
  } catch (e) {
    return { status: 0, data: null, ok: false }
  }
}

describe('Supabase REST smoke tests (prod, read-only)', () => {
  const skip = !SUPABASE_URL || !ANON_KEY

  beforeAll(() => {
    if (skip) {
      console.warn('SKIPPED: Supabase env not configured')
    }
  })

  it.skipIf(skip)('should expose so_engine_metadata view with verdicts_count and districts_count', async () => {
    const result = await fetchRest('/so_engine_metadata?select=*')
    expect(result.status).toBe(200)
    expect(Array.isArray(result.data)).toBe(true)
    expect(result.data.length).toBeGreaterThan(0)

    const meta = result.data[0]
    expect(meta).toHaveProperty('verdicts_count')
    expect(meta).toHaveProperty('districts_count')
    expect(meta.verdicts_count).toBeGreaterThan(0)
    expect(meta.districts_count).toBe(12)
  })

  it.skipIf(skip)('should expose so_district_map_features with exactly 12 districts', async () => {
    const result = await fetchRest('/so_district_map_features?select=id,name,composition_color')
    expect(result.status).toBe(200)
    expect(Array.isArray(result.data)).toBe(true)
    expect(result.data).toHaveLength(12)

    result.data.forEach((district: any) => {
      expect(['GREEN', 'ORANGE', 'RED', 'NONE']).toContain(district.composition_color)
    })
  })

  it.skipIf(skip)('should expose so_findings_public with severity in enum', async () => {
    const result = await fetchRest('/so_findings_public?select=*&limit=5')
    expect(result.status).toBe(200)

    if (result.data && result.data.length > 0) {
      result.data.forEach((finding: any) => {
        expect(['critical', 'high', 'medium', 'low', 'info']).toContain(finding.severity)
      })
    }
  })

  it.skipIf(skip)('should NOT expose raw verdicts table to anon', async () => {
    const result = await fetchRest('/verdicts?select=id')
    expect([401, 403, 404]).toContain(result.status)
  })

  it.skipIf(skip)('should expose so_district_scorecard with condition_order 1-9', async () => {
    const result = await fetchRest('/so_district_scorecard?select=district_id,condition_code,condition_order&limit=20')
    expect(result.status).toBe(200)

    if (result.data && result.data.length > 0) {
      result.data.forEach((row: any) => {
        expect(row.condition_order).toBeGreaterThanOrEqual(1)
        expect(row.condition_order).toBeLessThanOrEqual(9)
      })
    }
  })
})
