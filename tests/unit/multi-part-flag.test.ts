import { describe, it, expect } from 'vitest'
import {
  buildMultiPartByDistrict,
  buildDistrictSummaries,
} from '@/lib/compliance/school-popup'

// km² → m² helper for readable fixtures
const km2 = (n: number) => n * 1_000_000

describe('buildMultiPartByDistrict', () => {
  it('flags a district as multi-part only when >1 real part remains', () => {
    // Single-polygon district (one part) must NOT be flagged — that is the
    // whole point of Task A absorbing slivers: a clean obvod is silent.
    const single = buildMultiPartByDistrict([
      { district_id: 'd1', area_m2: km2(3.9) },
    ])
    expect(single['d1']).toBeUndefined()
  })

  it('orders parts largest-first and reports biggest + others in km²', () => {
    // Šrobárova-like: two comparable substantial bodies — must be surfaced,
    // not merged. The popup needs biggest + the rest for "najväčšia X, ostatné".
    const out = buildMultiPartByDistrict([
      { district_id: 'srob', area_m2: km2(0.27) },
      { district_id: 'srob', area_m2: km2(0.58) },
      { district_id: 'srob', area_m2: km2(0.61) },
    ])
    expect(out['srob'].parts).toBe(3)
    expect(out['srob'].biggestKm2).toBeCloseTo(0.61, 5)
    expect(out['srob'].otherKm2).toEqual([0.58, 0.27])
  })

  it('excludes demo seed parts from the real-part count', () => {
    // The Šmeralova demo segregation island (is_demo) must not inflate or
    // create a multi-part flag on its own — it is a separate demo overlay.
    const out = buildMultiPartByDistrict([
      { district_id: 'sme', area_m2: km2(1.28) },
      { district_id: 'sme', area_m2: km2(0.01), is_demo: true },
    ])
    // Only one real part → not multi-part despite the demo row present.
    expect(out['sme']).toBeUndefined()
  })
})

describe('buildDistrictSummaries multiPart wiring', () => {
  it('attaches the multiPart flag even when a district has no scorecard rows', () => {
    const multiPart = buildMultiPartByDistrict([
      { district_id: 'kup', area_m2: km2(10.9) },
      { district_id: 'kup', area_m2: km2(8.6) },
    ])
    const summaries = buildDistrictSummaries([], {}, multiPart)
    // Kúpeľná's 8.6 km² second body is substantial — it must reach the popup
    // as a review flag, scorecard or not.
    expect(summaries['kup'].multiPart?.parts).toBe(2)
    expect(summaries['kup'].multiPart?.biggestKm2).toBeCloseTo(10.9, 5)
  })
})
