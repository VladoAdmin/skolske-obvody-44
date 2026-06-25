import type { Metadata } from 'next'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { ConditionCard, SemaforCard } from '@/components/o-metodike-cards'

export const metadata: Metadata = {
  title: 'Ako hodnotíme — Kontrola § 44',
}

export default function OMetodikePage() {
  return (
    <article className="prose prose-sm max-w-3xl space-y-8">
      <DisclaimerBanner alwaysShow />

      <header>
        <h1 className="text-2xl font-semibold tracking-tight mb-2 not-prose">Metodika kontroly § 44</h1>
        <p className="text-muted-foreground leading-relaxed not-prose">
          Zákon č. 596/2003 Z. z. (§ 44) zaväzuje každú obec určiť školské obvody pre základné školy.
          Táto metodika popisuje, ako portál tieto obvody kontroluje — aké podmienky sa overujú,
          odkiaľ pochádzajú dáta a kde sú aktuálne medzery.
        </p>
      </header>

      <section>
        <h2 className="text-lg font-semibold mb-1 not-prose">Zákonné podmienky (Š)</h2>
        <p className="text-sm text-muted-foreground mb-4 not-prose">
          Tri podmienky priamo zo zákona č. 596/2003 § 44. Ich nesplnenie znamená porušenie zákona
          — preto majú priamy vplyv na semafor.
        </p>
        <div className="grid gap-3 sm:grid-cols-3 not-prose">
          <ConditionCard
            code="Š1"
            title="Adresy žiakov a obvod"
            body="Mapa adries všetkých žiakov musí spadať do správneho obvodu. Bez Registra adries to overiť nevieme — preto Š1 zatiaľ ostáva NEÚPLNÉ."
            type="law"
          />
          <ConditionCard
            code="Š2"
            title="Topologické pokrytie"
            body="Plocha obce musí byť pokrytá obvodmi bez medzier a bez prekryvov. Overujeme cez OSM geometriu."
            type="law"
          />
          <ConditionCard
            code="Š3"
            title="Kompozícia obvodu"
            body="Jeden obvod patrí jednej škole. Ak je v obvode viac škôl, ide o porušenie zákona."
            type="law"
          />
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-1 not-prose">Analytické indikátory (P-a až P-f)</h2>
        <p className="text-sm text-muted-foreground mb-4 not-prose">
          Šesť indikátorov, ktoré zákon explicitne nevymenúva, ale signalizujú rizikové situácie.
          Zlý indikátor posiela obvod do oranžovej, nie do červenej — sú to varovné signály, nie rozsudky.
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 not-prose">
          <ConditionCard
            code="P-a"
            title="Vzdialenosť ZŠ ≤ 2 km"
            body="Žiak 1. stupňa nemá mať školu vzdialenú viac než 2 km vzdušnou čiarou."
          />
          <ConditionCard
            code="P-b"
            title="Pešia trasa ≤ 30 min"
            body="Reálna pešia trasa nemá presahovať 30 minút (cca 2,5 km mestskou cestou)."
          />
          <ConditionCard
            code="P-c"
            title="MHD bez prestupu"
            body="Ak chodí žiak MHD-kou, prestup nesmie byť potrebný viac než raz. Ilustratívny indikátor — nezáväzný."
          />
          <ConditionCard
            code="P-d"
            title="Bezpečná trasa"
            body="Trasa z domu do školy neprekračuje rušnú cestu bez priechodu ani železnicu bez podchodu."
          />
          <ConditionCard
            code="P-e"
            title="Sociálny kontext (MRK)"
            body="Obvod nevylučuje deti z marginalizovaných komunít. Kontrolujeme voči Atlasu MRK — ide o signál, nie verdikt."
          />
          <ConditionCard
            code="P-f"
            title="Demografická prognóza"
            body="Demografická prognóza počtu detí v obvode súvisí s kapacitou školy. Odhadované z dát ŠTATSR."
          />
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-1 not-prose">Semaforová kompozícia</h2>
        <p className="text-sm text-muted-foreground mb-4 not-prose">
          Ako engine z 9 verdiktov vyrobí jednu farbu pre celý obvod:
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 not-prose">
          <SemaforCard
            color="green"
            title="🟢 Zelená"
            body="Všetky zákonné podmienky PASS a žiadne rizikové indikátory P-a až P-d."
          />
          <SemaforCard
            color="orange"
            title="🟠 Oranžová"
            body="Niektoré podmienky Š1–Š3 sú INCOMPLETE alebo indikátory P-a až P-d signalizujú riziko."
          />
          <SemaforCard
            color="red"
            title="🔴 Červená"
            body="Aspoň jedna zákonná podmienka Š1–Š3 je FAIL — priame porušenie zákona."
          />
          <SemaforCard
            color="gray"
            title="⚪ Sivá"
            body="Engine tento obvod ešte nehodnotil alebo chýba dostatok dát na akékoľvek hodnotenie."
          />
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-1 not-prose">Známe dátové medzery</h2>
        <ul className="space-y-2 text-sm not-prose">
          <li className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
            <strong>Register adries (Š1):</strong> nemáme prístup k adresám s trvalým pobytom žiakov →
            Š1 je zatiaľ INCOMPLETE pre všetkých 12 obvodov.
          </li>
          <li className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
            <strong>OSM hranice obvodov (Š2, Š3):</strong> nízka geometrická presnosť ručne digitalizovaných
            polygónov → Š2/Š3 môžu byť demoteované z FAIL na INCOMPLETE.
          </li>
          <li className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
            <strong>Demografia žiakov per ulica (P-e, P-f):</strong> chýba detailný rozklad →
            P-e a P-f sú len signál, nie záväzný verdikt.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-1 not-prose">Zdroje dát</h2>
        <ul className="space-y-1 text-sm text-muted-foreground not-prose list-disc list-inside">
          <li>WFS GIS (PSK) — obvody, školy, hranice obcí</li>
          <li>CVTI register škôl — ZŠ + MŠ s adresami</li>
          <li>OpenStreetMap — budovy, cestná sieť</li>
          <li>Atlas marginalizovaných rómskych komunít — MRK polygóny</li>
          <li>Google Maps API — geocoding adries Prešovských škôl, Routes API (P-c MHD)</li>
          <li>ŠTATSR — demografické odhady 6–15 r.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-1 not-prose">Verzie a transparentnosť</h2>
        <p className="text-sm text-muted-foreground not-prose">
          Engine verzia: <code className="rounded bg-muted px-1 font-mono text-xs">a4a3e85+demo</code> ·
          Metodika: <code className="rounded bg-muted px-1 font-mono text-xs">0.1</code> ·
          Posledný beh: 24. júna 2026.
        </p>
        <p className="text-sm text-muted-foreground mt-2 not-prose">
          Engine je deterministický Python skript — žiadne ML, čistá CASE logika. Zdrojový kód
          bude zverejnený na GitHub po internom review.
        </p>
      </section>
    </article>
  )
}
