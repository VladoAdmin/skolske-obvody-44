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
          Školské obvody — kontrola podľa § 44
        </h1>
        <div className="prose prose-sm text-muted-foreground space-y-3 max-w-none">
          <p>
            Každá obec na Slovensku má zo zákona (§ 44 zák. č. 596/2003 Z. z.) povinnosť určiť
            školské obvody pre základné školy. Obvod presne vymedzuje, ktoré ulice a adresy patria
            ku konkrétnej škole — žiak má právo nastúpiť do školy v obvode svojho trvalého pobytu.
          </p>
          <p>
            Tento portál vám ukáže, ako <strong>12 školských obvodov mesta Prešov</strong> obstojí
            v 9 merateľných podmienkach: tri zákonné požiadavky (Š1–Š3) a šesť analytických
            indikátorov dostupnosti (P-a až P-f). Dáta máme zatiaľ len pre Prešov. Výsledky sú
            informatívne — nie záväzný právny výklad.
          </p>
          <p>
            Každý obvod dostane farbu:{' '}
            <strong>🔴 červená</strong> = zákonné podmienky nesplnené,{' '}
            <strong>🟠 oranžová</strong> = dáta chýbajú alebo sú rizikové indikátory,{' '}
            <strong>🟢 zelená</strong> = všetko v poriadku,{' '}
            <strong>⚪ sivá</strong> = obvod sme ešte nehodnotili.
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
            description="Mesto Prešov, pilotné pokrytie"
          />
          <KpiCard
            label="Spracovaných verdiktov"
            value={meta?.verdicts_count ?? '—'}
            description="12 obvodov × 9 podmienok"
          />
          <KpiCard
            label="Otvorených nálezov"
            value={summary?.open_findings_count ?? meta?.open_findings_count ?? '—'}
            description="Stav po poslednom výpočte"
          />
        </dl>
      </section>

      {/* Portal section cards */}
      <section aria-labelledby="quick-access-heading" className="space-y-4">
        <h2 id="quick-access-heading" className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Sekcie portálu
        </h2>
        <nav aria-label="Hlavné sekcie portálu">
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 list-none p-0 m-0">
            {PORTAL_CARDS.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="block rounded-lg border border-border p-5 hover:border-primary hover:bg-accent/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="block text-lg mb-1">{item.icon}</span>
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

const PORTAL_CARDS = [
  { href: '/map', icon: '🗺️', label: 'Mapa obvodov', description: 'Zobrazte si obvody na mape — kde sú školy, kde žijú deti a kde sú nálezy' },
  { href: '/findings', icon: '📋', label: 'Register nálezov', description: 'Prehľad konkrétnych problémov — každý nález má závažnosť a dôkaz' },
  { href: '/municipalities', icon: '🏛️', label: 'Zriaďovatelia', description: 'Ktoré obce sme preverili a koľko otvorených nálezov majú' },
  { href: '/o-metodike', icon: '📖', label: 'Ako hodnotíme', description: 'Čo sú podmienky Š1–Š3, čo sú indikátory P-a až P-f a ako funguje semafor' },
] as const
