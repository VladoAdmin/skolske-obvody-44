import Link from 'next/link'
import { KpiCard } from '@/components/kpi-card'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { createPublicClient } from '@/lib/supabase/server'
import type { EngineMetadata, MunicipalitySummary } from '@/lib/supabase/types'

export const revalidate = 300

async function fetchKpis() {
  try {
    const sb = createPublicClient()
    const [metaRes, summaryRes] = await Promise.all([
      sb.from('so_engine_metadata').select('*').maybeSingle(),
      sb.from('so_municipalities_summary').select('*').maybeSingle(),
    ])
    return {
      meta: metaRes.data as EngineMetadata | null,
      summary: summaryRes.data as MunicipalitySummary | null,
    }
  } catch {
    return { meta: null, summary: null }
  }
}

export default async function Home() {
  const { meta, summary } = await fetchKpis()

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <DisclaimerBanner />

      <section aria-labelledby="portal-heading">
        <h1 id="portal-heading" className="text-2xl font-semibold tracking-tight mb-3">
          Kontrola § 44 — Školské obvody
        </h1>
        <div className="prose prose-sm text-muted-foreground space-y-3 max-w-none">
          <p>
            Zákon č. 596/2003 Z. z. (§ 44) ukladá mestám a obciam povinnosť určiť školské obvody
            pre žiakov základných škôl. Obvody musia spĺňať požiadavky na dostupnosť školy
            (vzdialenosť, pešia trasa, MHD), topolologickú konzistentnosť hraníc a demografickú
            a sociálnu primeranosť.
          </p>
          <p>
            Tento analytický portál overuje súlad školských obvodov mesta <strong>Prešov</strong>{' '}
            s podmienkami § 44. Pilot pokrýva <strong>12 schulských obvodov</strong> v 9 merateľných
            podmienkach (Š1–Š3 zákonné, P-a až P-f rizikové indikátory). Výsledky sú informatívne
            a slúžia ako podklad pre rozhodovanie — nie ako záväzný právny výklad.
          </p>
          <p>
            Semaforová kompozícia: <strong>ČERVENÁ</strong> = zákonné podmienky nesplnené,{' '}
            <strong>ORANŽOVÁ</strong> = neúplné dáta alebo rizikové indikátory,{' '}
            <strong>ZELENÁ</strong> = všetky zákonné podmienky splnené. Sivá = engine ešte
            nezhodnotil.
          </p>
        </div>
      </section>

      {/* KPI cards */}
      <section aria-labelledby="kpi-heading">
        <h2 id="kpi-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
          Stav dát
        </h2>
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <KpiCard
            label="Posúdených obvodov"
            value={summary?.districts_count ?? meta?.districts_count ?? '—'}
            description="Prešovský samosprávny kraj"
          />
          <KpiCard
            label="Spracovaných verdiktov"
            value={meta?.verdicts_count ?? '—'}
            description="9 podmienok × obvody"
          />
          <KpiCard
            label="Otvorených nálezov"
            value={summary?.open_findings_count ?? meta?.open_findings_count ?? '—'}
            description="Stav k poslednému engine behu"
          />
        </dl>
      </section>

      {/* CTA */}
      <section>
        <Link
          href="/map"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Otvoriť mapu PSK →
        </Link>
      </section>

      {/* Quick nav */}
      <section aria-labelledby="quick-access-heading" className="space-y-4">
        <h2 id="quick-access-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Sekcie portálu
        </h2>
        <nav aria-label="Hlavné sekcie portálu">
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 list-none p-0 m-0">
            {NAV_ITEMS.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="block rounded-lg border border-border p-4 hover:bg-accent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="block font-medium text-sm">{item.label}</span>
                  <span className="block text-xs text-muted-foreground mt-1">{item.description}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </section>
    </div>
  )
}

const NAV_ITEMS = [
  { href: '/map', label: 'Mapa PSK', description: 'Farebná mapa 12 školských obvodov so semaforom' },
  { href: '/findings', label: 'Register nálezov', description: 'Filtrovaný zoznam odchýlok a rizík' },
  { href: '/municipalities', label: 'Zriaďovatelia', description: 'Súhrnný scorecard per obec' },
  { href: '/o-metodike', label: 'O metodike', description: 'Podmienky § 44, semaforová logika, GAP-y' },
] as const
