import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { getGoogleRoute } from '@/services/routing-google/client'

// Google Routes API v2 (computeRoutes) responses, mocked — no real network
// calls. Mirrors the "never fabricate straight-line" contract of
// services/routing/client.ts: every no-route / error response must map to
// low_data/unavailable, never a guessed distance.
//
// Response shapes verified live against the real API before writing these
// mocks: no-route -> HTTP 200 with an empty body ({}); auth/request errors
// -> non-2xx with an { error: ... } body.

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
          routes: [
            {
              distanceMeters: 2345.6,
              duration: '1800s',
              polyline: { encodedPolyline: 'abc123' },
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

  it('sends travelMode WALK/TRANSIT and the field mask header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ routes: [{ distanceMeters: 100, duration: '60s', polyline: { encodedPolyline: 'x' } }] })
    )
    vi.stubGlobal('fetch', fetchMock)

    await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'transit' })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('routes.googleapis.com/directions/v2:computeRoutes')
    expect(init.method).toBe('POST')
    expect(init.headers['X-Goog-Api-Key']).toBe('test-key')
    expect(init.headers['X-Goog-FieldMask']).toContain('transitDetails')
    const body = JSON.parse(init.body)
    expect(body.travelMode).toBe('TRANSIT')
    expect(body.origin.location.latLng).toEqual({ latitude: ORIGIN[1], longitude: ORIGIN[0] })
  })

  it('extracts a transit line label for mode=transit', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          routes: [
            {
              distanceMeters: 9000,
              duration: '1500s',
              polyline: { encodedPolyline: 'xyz789' },
              legs: [
                {
                  steps: [
                    { travelMode: 'WALK' },
                    {
                      travelMode: 'TRANSIT',
                      transitDetails: { transitLine: { nameShort: '22', vehicle: { name: { text: 'Autobus' } } } },
                    },
                  ],
                },
              ],
            },
          ],
        })
      )
    )

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'transit' })

    expect(result.status).toBe('ok')
    expect(result.transitLine).toBe('Autobus 22')
  })

  it('returns low_data when the API returns no routes (HTTP 200, empty body) — never fabricates a straight-line distance', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({})))

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'walking' })

    expect(result).toEqual({ status: 'low_data' })
  })

  it('returns unavailable on a non-2xx HTTP response (e.g. invalid API key)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ error: { code: 400, status: 'INVALID_ARGUMENT' } }, false))
    )

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'walking' })

    expect(result).toEqual({ status: 'unavailable' })
  })

  it('returns unavailable when fetch throws (network error)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    const result = await getGoogleRoute({ origin: ORIGIN, destination: DEST, mode: 'walking' })

    expect(result).toEqual({ status: 'unavailable' })
  })
})
