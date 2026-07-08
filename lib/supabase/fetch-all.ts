import type { SupabaseClient } from '@supabase/supabase-js'

// PostgREST caps every response at 1000 rows (server max-rows), silently
// truncating larger selects — so_district_street_linestrings has ~3000 rows
// and rendered with whole neighbourhoods missing before sprint 5. Any select
// from a view that can exceed 1000 rows MUST go through this helper.
const PAGE_SIZE = 1000

// range() alone does not guarantee row order is stable across the successive
// queries a paged fetch issues — without an ORDER BY, Postgres can return a
// row twice or skip it if a write or query-plan change lands between pages.
// orderBy must name a column that is unique for every row of `table`, or the
// same gap/duplicate risk reappears for rows tied on that column.
export async function fetchAllRows<T>(
  sb: SupabaseClient,
  table: string,
  select: string,
  orderBy: string
): Promise<T[]> {
  const rows: T[] = []
  for (let from = 0; ; from += PAGE_SIZE) {
    const { data, error } = await sb
      .from(table)
      .select(select)
      .order(orderBy, { ascending: true })
      .range(from, from + PAGE_SIZE - 1)
    if (error) throw error
    const page = (data ?? []) as T[]
    rows.push(...page)
    if (page.length < PAGE_SIZE) return rows
  }
}
