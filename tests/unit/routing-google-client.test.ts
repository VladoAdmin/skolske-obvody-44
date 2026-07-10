import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { getGoogleRoute } from '@/services/routing-google/client'

// Google Directions API responses, mocked — no real network calls. Mirrors
// the "never fabricate straight-line" contract of services/routing/client.ts:
// every non-OK API status must map to low_data/unavailable, never a guessed
// distance.

const ORIGIN: [number, number] = [21.2611, 49.0014]
const DEST: [number, number] = [21.24, 49.02]

function jsonResponse(body: unknown, ok = true) {
  return {
    ok,
    json: async () => body,
  } as Response
}

describe('getGoogleRoute', () => {
  const originalKey = process.env.GOOGLE_API_KEY

  beforeEach(() => {
    process.env.GOOGLE_API_KEY = 'test-key'
  })

  afterEach(() => {
    process.env.GOOGLE_API_KEY = originalKey
    vi.unstubAllGlobals()
  })

  it('returns unavailable when GOOGLE_API_KEY is not set', async () => {
    delete process.env.GOOGLE_API_KEY
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'walking' })

    expect(result).toEqual({ status: 'unavailable' })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('parses a successful walking route (status ok, distance/duration/polyline)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          status: 'OK',
          routes: [
            {
              legs: [{ distance: { value: 2345.6 }, duration: { value: 1800.2 } }],
              overview_polyline: { points: 'abc123' },
            },
          ],
        })
      )
    )

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'walking' })

    expect(result).toEqual({
      status: 'ok',
      distanceMetres: 2346,
      durationSeconds: 1800,
      encodedPolyline: 'abc123',
      transitLine: undefined,
    })
  })

  it('extracts a transit line label for mode=transit', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          status: 'OK',
          routes: [
            {
              legs: [
                {
                  distance: { value: 9000 },
                  duration: { value: 1500 },
                  steps: [
                    { travel_mode: 'WALKING' },
                    {
                      travel_mode: 'TRANSIT',
                      transit_details: { line: { short_name: '22', vehicle: { name: 'Autobus' } } },
                    },
                  ],
                },
              ],
              overview_polyline: { points: 'xyz789' },
            },
          ],
        })
      )
    )

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'transit' })

    expect(result.status).toBe('ok')
    expect(result.transitLine).toBe('Autobus 22')
  })

  it('returns low_data on ZERO_RESULTS — never fabricates a straight-line distance', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ status: 'ZERO_RESULTS' })))

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'walking' })

    expect(result).toEqual({ status: 'low_data' })
  })

  it('returns unavailable on an API-level error status (e.g. REQUEST_DENIED)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ status: 'REQUEST_DENIED' })))

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'walking' })

    expect(result).toEqual({ status: 'unavailable' })
  })

  it('returns unavailable on a non-2xx HTTP response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, false)))

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'walking' })

    expect(result).toEqual({ status: 'unavailable' })
  })

  it('returns unavailable when fetch throws (network error)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'walking' })

    expect(result).toEqual({ status: 'unavailable' })
  })
})
