import { describe, it, expect } from 'vitest'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || ''
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || ''
const skip = !SUPABASE_URL || !SERVICE_KEY

async function callSanitize(input: string): Promise<string> {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/f2_query_sql`, {
    method: 'POST',
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: `SELECT skolske_obvody.sanitize_evidence('${input.replace(/'/g, "''")}', 500) AS out`,
    }),
  })
  const json = await res.json()
  return json.rows[0].out as string
}

describe('PII sanitization (sanitize_evidence)', () => {
  it.skipIf(skip)('strips SK mobile 0903 format', async () => {
    const out = await callSanitize('kontakt 0903 123 456 koniec')
    expect(out).toBe('kontakt [tel] koniec')
  })

  it.skipIf(skip)('strips SK mobile with hyphens', async () => {
    const out = await callSanitize('volaj 0911-222-333')
    expect(out).toBe('volaj [tel]')
  })

  it.skipIf(skip)('strips SK landline 02 1234 5678', async () => {
    const out = await callSanitize('stacionar 02 1234 5678')
    expect(out).toBe('stacionar [tel]')
  })

  it.skipIf(skip)('strips +421 international prefix', async () => {
    const out = await callSanitize('+421 905 123 456')
    expect(out).toBe('[tel]')
  })

  it.skipIf(skip)('strips 00421 international prefix', async () => {
    const out = await callSanitize('00421 911 222 333')
    expect(out).toBe('[tel]')
  })

  it.skipIf(skip)('strips email', async () => {
    const out = await callSanitize('email jan.novak@example.com koniec')
    expect(out).toBe('email [email] koniec')
  })

  it.skipIf(skip)('strips SK rodné číslo format', async () => {
    const out = await callSanitize('rodne cislo 880101/1234')
    expect(out).toBe('rodne cislo [rč]')
  })

  it.skipIf(skip)('handles compound PII', async () => {
    const out = await callSanitize('email a@b.sk a tel 0905 999 888')
    expect(out).toBe('email [email] a tel [tel]')
  })

  it.skipIf(skip)('passes through clean text unchanged', async () => {
    const out = await callSanitize('normalny text bez PII data')
    expect(out).toBe('normalny text bez PII data')
  })

  it.skipIf(skip)('truncates to max_len', async () => {
    const out = await callSanitize('x'.repeat(100))
    expect(out.length).toBeLessThanOrEqual(500)
  })
})
