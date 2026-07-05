import type { SupabaseClient } from '@supabase/supabase-js'

// PostgREST caps every response at 1000 rows (server max-rows), silently
// truncating larger selects — so_district_street_linestrings has ~3000 rows
// and rendered with whole neighbourhoods missing before sprint 5. Any select
// from a view that can exceed 1000 rows MUST go through this helper.
const PAGE_SIZE = 1000

export async function fetchAllRows<T>(
  sb: SupabaseClient,
  table: string,
  select: string
): Promise<T[]> {
  const rows: T[] = []
  for (let from = 0; ; from += PAGE_SIZE) {
    const { data, error } = await sb
      .from(table)
      .select(select)
      .range(from, from + PAGE_SIZE - 1)
    if (error) throw error
    const page = (data ?? []) as T[]
    rows.push(...page)
    if (page.length < PAGE_SIZE) return rows
  }
}
