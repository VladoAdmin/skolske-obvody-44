import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export function createPublicClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

  return createServerClient(
    supabaseUrl,
    supabaseAnonKey,
    {
      cookies: {
        get: (n) => cookies().get(n)?.value,
        set() {}, // read-only client — no writes
        remove() {},
      },
      db: { schema: 'public' },
    },
  )
}
