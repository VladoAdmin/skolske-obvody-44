import { describe, it, expect } from 'vitest'
import type { SupabaseClient } from '@supabase/supabase-js'
import { fetchAllRows } from '@/lib/supabase/fetch-all'

// PostgREST caps every response at 1000 rows. fetchAllRows exists so that a
// view larger than one page (so_district_street_linestrings: 2974 segments)
// is fetched COMPLETELY — before sprint 5 the map silently dropped rows
// 1001+ and rendered whole neighbourhoods uncoloured.

// Stub client that serves `total` rows in PostgREST-capped pages and records
// the requested ranges and the order column each page was requested with.
function makeStubClient(total: number, error: { message: string } | null = null) {
  const ranges: Array<[number, number]> = []
  const orderCols: string[] = []
  const sb = {
    from: () => ({
      select: () => ({
        order: (col: string) => {
          orderCols.push(col)
          return {
            range: async (from: number, to: number) => {
              ranges.push([from, to])
              if (error) return { data: null, error }
              const n = Math.max(0, Math.min(total - from, to - from + 1))
              const data = Array.from({ length: n }, (_, i) => ({ id: from + i }))
              return { data, error: null }
            },
          }
        },
      }),
    }),
  }
  return { sb: sb as unknown as SupabaseClient, ranges, orderCols }
}

describe('fetchAllRows (PostgREST 1000-row cap)', () => {
  it('fetches ALL rows of a >1000-row view, not just the first page', async () => {
    const { sb, ranges } = makeStubClient(2974)
    const rows = await fetchAllRows<{ id: number }>(sb, 'view', 'id', 'id')
    expect(rows).toHaveLength(2974)
    // No duplicates / gaps — last row is the 2974th.
    expect(rows[2973]).toEqual({ id: 2973 })
    expect(ranges).toEqual([[0, 999], [1000, 1999], [2000, 2999]])
  })

  it('applies the given orderBy column to every page', async () => {
    const { sb, orderCols } = makeStubClient(2974)
    await fetchAllRows<{ id: number }>(sb, 'view', 'id', 'segment_id')
    expect(orderCols).toEqual(['segment_id', 'segment_id', 'segment_id'])
  })

  it('terminates when the row count is an exact multiple of the page size', async () => {
    const { sb, ranges } = makeStubClient(2000)
    const rows = await fetchAllRows<{ id: number }>(sb, 'view', 'id', 'id')
    expect(rows).toHaveLength(2000)
    // One trailing empty page is the stop signal — never an infinite loop.
    expect(ranges).toHaveLength(3)
  })

  it('returns a sub-page result in a single request', async () => {
    const { sb, ranges } = makeStubClient(12)
    const rows = await fetchAllRows<{ id: number }>(sb, 'view', 'id', 'id')
    expect(rows).toHaveLength(12)
    expect(ranges).toHaveLength(1)
  })

  it('throws on a PostgREST error so callers keep their own fallback', async () => {
    const { sb } = makeStubClient(10, { message: 'boom' })
    await expect(fetchAllRows(sb, 'view', 'id', 'id')).rejects.toEqual({ message: 'boom' })
  })
})
