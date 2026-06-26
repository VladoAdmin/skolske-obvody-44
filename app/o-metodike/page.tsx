import type { Metadata } from 'next'
import Image from 'next/image'
import { DisclaimerBanner } from '@/components/disclaimer-banner'
import { ConditionCard, SemaforCard } from '@/components/o-metodike-cards'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export const metadata: Metadata = {
  title: 'Ako hodnotíme — Kontrola § 44',
}

const TOC_ITEMS: Array<{ id: string; label: string }> = [
  { id: 'zakonne-podmienky', label: 'Zákonné podmienky (Š)' },
  { id: 'analyticke-indikatory', label: 'Analytické indikátory (P)' },
  { id: 'semafor', label: 'Semaforová kompozícia' },
  { id: 'datove-medzery', label: 'Známe dátové medzery' },
  { id: 'zdroje-dat', label: 'Zdroje dát' },
  { id: 'data-pipeline', label: 'Ako získavame dáta o obvodoch' },
  { id: 'paragraf-44', label: 'Ako vyhodnocujeme § 44 zákona 321' },
  { id: 'priklady', label: 'Príklady z praxe' },
  { id: 'co-robime', label: 'Čo robíme, čo nerobíme' },
  { id: 'verzie', label: 'Verzie a transparentnosť' },
]

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

      {/* Sub-navigation / TOC */}
      <nav
        aria-label="Obsah metodiky"
        className="not-prose rounded-lg border border-border bg-muted/30 p-4"
      >
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
          Obsah
        </p>
        <ol className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2 list-decimal list-inside marker:text-muted-foreground">
          {TOC_ITEMS.map(item => (
            <li key={item.id}>
              <a
                href={`#${item.id}`}
                className="text-primary hover:underline underline-offset-2"
              >
                {item.label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <section id="zakonne-podmienky" className="scroll-mt-20">
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

      <section id="analyticke-indikatory" className="scroll-mt-20">
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

      <section id="semafor" className="scroll-mt-20">
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

      <section id="datove-medzery" className="scroll-mt-20">
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

      <section id="zdroje-dat" className="scroll-mt-20">
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

      {/* ===== Sprint M-4: new sections ===== */}

      {/* Section 1: data pipeline */}
      <section id="data-pipeline" className="scroll-mt-20">
        <h2 className="text-lg font-semibold mb-1 not-prose">Ako získavame dáta o školských obvodoch</h2>
        <p className="text-sm text-muted-foreground mb-4 not-prose">
          Cesta od textu vo VZN po polygón obvodu má päť deterministických krokov.
          Žiadne ručné kreslenie čiar na mape — všetko vychádza zo zverejneného VZN
          a verejných adresných databáz.
        </p>

        <div className="not-prose space-y-4">
          <ol className="space-y-3">
            <li className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-baseline gap-2 mb-1">
                <span className="inline-block rounded bg-primary/10 px-2 py-0.5 font-mono text-xs font-bold text-primary">1</span>
                <span className="text-sm font-semibold">Scraping VZN</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Z úradných tabúľ a VZN sekcií mestských webov sťahujeme PDF a HTML
                dokumenty. Z textu (typicky príloha k VZN o sieti ZŠ) extrahujeme
                pasáže, ktoré definujú školské obvody — názvy ulíc a rozsahy čísiel
                domov priradené jednotlivým školám.
              </p>
            </li>

            <li className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-baseline gap-2 mb-1">
                <span className="inline-block rounded bg-primary/10 px-2 py-0.5 font-mono text-xs font-bold text-primary">2</span>
                <span className="text-sm font-semibold">Parser ulíc</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Žargón VZN typu &bdquo;Bajkalská 1–47 párne&ldquo; rozkladáme na
                konkrétne čísla domov (1, 3, 5, &hellip;, 47). Rovnako rozpoznáváme
                nepárne rozsahy, intervaly &bdquo;od&hellip;po&ldquo; a výnimky
                (&bdquo;okrem 12, 14&ldquo;). Výsledok je tabuľka{' '}
                <em>ulica + číslo domu → škola</em>.
              </p>
            </li>

            <li className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-baseline gap-2 mb-1">
                <span className="inline-block rounded bg-primary/10 px-2 py-0.5 font-mono text-xs font-bold text-primary">3</span>
                <span className="text-sm font-semibold">Geokódovanie</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Každú dvojicu ulica + číslo domu posielame do Google Geocoding API
                a získavame presné GPS súradnice. Pilot pre Prešov stál približne
                $2,56 a vrátil 460 platných adresných bodov z 513 hľadaných
                (~89,7 % presnosť). Záznamy bez plnej zhody (<code>partial_match</code>)
                označujeme a vylučujeme z hraničných výpočtov.
              </p>
            </li>

            <li className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-baseline gap-2 mb-1">
                <span className="inline-block rounded bg-primary/10 px-2 py-0.5 font-mono text-xs font-bold text-primary">4</span>
                <span className="text-sm font-semibold">Priradenie do obvodu</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Každému geokódovanému domu pripíšeme atribút &bdquo;patrí do obvodu X&ldquo;
                podľa VZN. Tu sa odhalia priame chyby v texte — napríklad keď tá istá
                ulica je v dvoch obvodoch súčasne (potenciálne porušenie § 44 Š2).
              </p>
            </li>

            <li className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-baseline gap-2 mb-1">
                <span className="inline-block rounded bg-primary/10 px-2 py-0.5 font-mono text-xs font-bold text-primary">5</span>
                <span className="text-sm font-semibold">Rekonštrukcia obvodu</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Z geokódovaných domov a uličnej siete OSM vyrenderujeme plochu obvodu
                (Voronoi tessellation + snap na ulice). Tento polygón nereprezentuje
                oficiálnu mapu samosprávy — je to vizuálna rekonštrukcia toho, čo VZN
                text v skutočnosti hovorí.
              </p>
            </li>
          </ol>

          {/* inline SVG flow diagram */}
          <figure className="rounded-lg border border-border bg-muted/20 p-4">
            <svg
              role="img"
              aria-label="Diagram dátového toku: VZN scrape → parser ulíc → geokódovanie → priradenie do obvodu → rekonštrukcia polygónu"
              viewBox="0 0 720 80"
              className="w-full h-auto"
            >
              {[
                { x: 0, label: 'VZN scrape' },
                { x: 145, label: 'Parser ulíc' },
                { x: 290, label: 'Geokódovanie' },
                { x: 435, label: 'Priradenie' },
                { x: 580, label: 'Polygón obvodu' },
              ].map((node, idx, arr) => (
                <g key={node.label}>
                  <rect
                    x={node.x}
                    y={20}
                    width={140}
                    height={40}
                    rx={6}
                    fill="#ffffff"
                    stroke="#94a3b8"
                    strokeWidth={1.5}
                  />
                  <text
                    x={node.x + 70}
                    y={45}
                    textAnchor="middle"
                    fontSize="12"
                    fill="#0f172a"
                    fontFamily="ui-sans-serif, system-ui, sans-serif"
                    fontWeight={600}
                  >
                    {node.label}
                  </text>
                  {idx < arr.length - 1 && (
                    <path
                      d={`M ${node.x + 140} 40 L ${arr[idx + 1].x} 40`}
                      stroke="#64748b"
                      strokeWidth={1.5}
                      markerEnd="url(#arrow)"
                      fill="none"
                    />
                  )}
                </g>
              ))}
              <defs>
                <marker
                  id="arrow"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
                </marker>
              </defs>
            </svg>
            <figcaption className="mt-2 text-xs text-muted-foreground text-center">
              Tok dát: text VZN → adresné body → polygón obvodu.
              Každý krok je deterministický a auditovateľný.
            </figcaption>
          </figure>
        </div>
      </section>

      {/* Section 2: § 44 evaluation criteria */}
      <section id="paragraf-44" className="scroll-mt-20">
        <h2 className="text-lg font-semibold mb-1 not-prose">Ako vyhodnocujeme § 44 zákona 321</h2>
        <p className="text-sm text-muted-foreground mb-4 not-prose">
          Engine kontroluje šesť konkrétnych kritérií. Pre každé vieme presne povedať,
          aký vstup berieme, aký test robíme a aké výsledky sú možné. Kritéria so
          symbolom <strong>Š</strong> pochádzajú priamo zo zákona, kritériá{' '}
          <strong>P</strong> sú analytické indikátory rizika.
        </p>

        <div className="not-prose rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40">
                <TableHead className="w-14">Kód</TableHead>
                <TableHead>Názov</TableHead>
                <TableHead className="hidden md:table-cell">Otázka zákona</TableHead>
                <TableHead>Čo vyhodnocujeme</TableHead>
                <TableHead className="w-36">Možný výsledok</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow className="align-top">
                <TableCell className="font-mono text-xs font-bold text-red-800">Š1</TableCell>
                <TableCell className="whitespace-normal text-xs font-medium">Úplnosť obvodu</TableCell>
                <TableCell className="hidden md:table-cell whitespace-normal text-xs text-muted-foreground">
                  Pokrýva VZN všetky deti v obci?
                </TableCell>
                <TableCell className="whitespace-normal text-xs text-muted-foreground">
                  Porovnávame adresy v obvodoch s Registrom adries MŠSR.
                  Príklad: ak na Bajkalskej býva 47 detí a VZN ich uvádza 45, dva
                  prípady ostávajú bez priradenej školy.
                </TableCell>
                <TableCell className="whitespace-normal text-xs">
                  <span className="inline-block rounded bg-amber-100 px-1.5 py-0.5 font-mono text-[10px] text-amber-900">
                    INSUFFICIENT_DATA
                  </span>
                  <span className="block text-muted-foreground mt-1">
                    register MŠSR nedostupný
                  </span>
                </TableCell>
              </TableRow>

              <TableRow className="align-top">
                <TableCell className="font-mono text-xs font-bold text-red-800">Š2</TableCell>
                <TableCell className="whitespace-normal text-xs font-medium">Disjunktívnosť</TableCell>
                <TableCell className="hidden md:table-cell whitespace-normal text-xs text-muted-foreground">
                  Patrí každá adresa práve do jedného obvodu?
                </TableCell>
                <TableCell className="whitespace-normal text-xs text-muted-foreground">
                  Identifikujeme prekryvy medzi obvodmi. Príklad: ak ZŠ A aj ZŠ B
                  vo svojom VZN texte uvádzajú Bajkalskú 12, je to prekryv a Š2 FAIL.
                </TableCell>
                <TableCell className="whitespace-normal text-xs">
                  <span className="inline-block rounded bg-green-100 px-1.5 py-0.5 font-mono text-[10px] text-green-900">PASS</span>{' / '}
                  <span className="inline-block rounded bg-red-100 px-1.5 py-0.5 font-mono text-[10px] text-red-900">FAIL</span>
                </TableCell>
              </TableRow>

              <TableRow className="align-top">
                <TableCell className="font-mono text-xs font-bold text-red-800">Š3</TableCell>
                <TableCell className="whitespace-normal text-xs font-medium">Žiadna segregácia</TableCell>
                <TableCell className="hidden md:table-cell whitespace-normal text-xs text-muted-foreground">
                  Sú obvody navrhnuté tak, že nesegregujú menšinové deti?
                </TableCell>
                <TableCell className="whitespace-normal text-xs text-muted-foreground">
                  Polygóny obvodov krížime s Atlasom MRK a hľadáme ostrovy
                  (fragmenty odtrhnuté od hlavnej plochy). Príklad: ostrov 30 domov
                  na okraji rómskej osady patriaci pod inú školu = RISK na Š3.
                </TableCell>
                <TableCell className="whitespace-normal text-xs">
                  <span className="inline-block rounded bg-green-100 px-1.5 py-0.5 font-mono text-[10px] text-green-900">PASS</span>{' / '}
                  <span className="inline-block rounded bg-orange-100 px-1.5 py-0.5 font-mono text-[10px] text-orange-900">RISK</span>{' / '}
                  <span className="inline-block rounded bg-red-100 px-1.5 py-0.5 font-mono text-[10px] text-red-900">FAIL</span>
                </TableCell>
              </TableRow>

              <TableRow className="align-top">
                <TableCell className="font-mono text-xs font-bold text-red-800">Š4</TableCell>
                <TableCell className="whitespace-normal text-xs font-medium">Konzistencia s realitou</TableCell>
                <TableCell className="hidden md:table-cell whitespace-normal text-xs text-muted-foreground">
                  Existuje každá adresa v zoznamoch?
                </TableCell>
                <TableCell className="whitespace-normal text-xs text-muted-foreground">
                  Validácia cez Google Geocoding — pozeráme na{' '}
                  <code className="rounded bg-muted px-1 font-mono text-[10px]">formatted_address</code>{' '}
                  a flag <code className="rounded bg-muted px-1 font-mono text-[10px]">partial_match</code>.
                  Príklad: VZN uvádza &bdquo;Lipová 99&ldquo;, ale na Lipovej je
                  najvyššie č. 47 → adresa neexistuje, Š4 FAIL pre tento záznam.
                </TableCell>
                <TableCell className="whitespace-normal text-xs">
                  <span className="inline-block rounded bg-green-100 px-1.5 py-0.5 font-mono text-[10px] text-green-900">PASS</span>{' / '}
                  <span className="inline-block rounded bg-red-100 px-1.5 py-0.5 font-mono text-[10px] text-red-900">FAIL</span>
                </TableCell>
              </TableRow>

              <TableRow className="align-top">
                <TableCell className="font-mono text-xs font-bold text-primary">Pa</TableCell>
                <TableCell className="whitespace-normal text-xs font-medium">Spádová kapacita</TableCell>
                <TableCell className="hidden md:table-cell whitespace-normal text-xs text-muted-foreground">
                  Má škola kapacitu pre deti v obvode?
                </TableCell>
                <TableCell className="whitespace-normal text-xs text-muted-foreground">
                  Počet detí 6–15 r. v obvode (WFS demografia) porovnávame
                  s kapacitou budov ZŠ (EDUZBER). Príklad: obvod má 280 detí,
                  budova ZŠ má kapacitu 240 miest → Pa RISK.
                </TableCell>
                <TableCell className="whitespace-normal text-xs">
                  <span className="inline-block rounded bg-amber-100 px-1.5 py-0.5 font-mono text-[10px] text-amber-900">
                    INSUFFICIENT_DATA
                  </span>
                  <span className="block text-muted-foreground mt-1">EDUZBER nedostupný — proxy</span>
                </TableCell>
              </TableRow>

              <TableRow className="align-top">
                <TableCell className="font-mono text-xs font-bold text-primary">Pb</TableCell>
                <TableCell className="whitespace-normal text-xs font-medium">Pešia trasa</TableCell>
                <TableCell className="hidden md:table-cell whitespace-normal text-xs text-muted-foreground">
                  Je pre 1. stupeň ZŠ pešia trasa ≤ 2 km?
                </TableCell>
                <TableCell className="whitespace-normal text-xs text-muted-foreground">
                  OSM routing počíta reálnu pešiu vzdialenosť od domu po školu
                  (nie vzdušnú čiaru). Príklad: dom je 1,1 km vzdušnou čiarou,
                  ale cez most a obchádzku je to 2,4 km → Pb RISK pre 1. stupeň.
                </TableCell>
                <TableCell className="whitespace-normal text-xs">
                  <span className="inline-block rounded bg-green-100 px-1.5 py-0.5 font-mono text-[10px] text-green-900">PASS</span>{' / '}
                  <span className="inline-block rounded bg-orange-100 px-1.5 py-0.5 font-mono text-[10px] text-orange-900">RISK</span>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <p className="text-xs text-muted-foreground mt-3 not-prose">
          Verdikt celého obvodu vzniká kompozíciou: ktorékoľvek <strong>Š</strong> FAIL
          posúva obvod do červenej (§ 44 porušený). Indikátory <strong>P</strong> RISK
          posúvajú do oranžovej (varovanie, nie porušenie zákona). Detaily v sekcii{' '}
          <a href="#semafor" className="text-primary hover:underline">Semaforová kompozícia</a>.
        </p>
      </section>

      {/* Section 3: real-world examples */}
      <section id="priklady" className="scroll-mt-20">
        <h2 className="text-lg font-semibold mb-1 not-prose">Príklady z praxe</h2>
        <p className="text-sm text-muted-foreground mb-4 not-prose">
          Tri typické situácie, na ktoré naráža engine v reálnych mestách.
          Ilustrácie zachytávajú podstatu — ako vyzerajú správne hranice,
          ako vyzerá prekryv a ako vyzerá fragment-ostrov.
        </p>

        <div className="not-prose grid gap-4 md:grid-cols-3">
          <figure className="rounded-lg border border-border bg-card p-3 space-y-2">
            <div className="relative aspect-[10/7] w-full overflow-hidden rounded-md bg-muted/30">
              <Image
                src="/methodology/example-clean.svg"
                alt="Ilustrácia správneho obvodu: tri obvody bez prekryvov, hranice po uliciach"
                width={400}
                height={280}
                className="h-auto w-full"
              />
            </div>
            <figcaption className="space-y-1">
              <p className="text-sm font-semibold">1. Správny obvod</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Clean polygón ZŠ Bajkalská. Hranice idú po uliciach, žiadne
                prekryvy ani ostrovy, zelené body adresných domov sedia
                vo svojom obvode. Toto je cieľový stav — engine nevyhlasuje
                žiadny nález, semafor zelený.
              </p>
            </figcaption>
          </figure>

          <figure className="rounded-lg border border-border bg-card p-3 space-y-2">
            <div className="relative aspect-[10/7] w-full overflow-hidden rounded-md bg-muted/30">
              <Image
                src="/methodology/example-overlap.svg"
                alt="Ilustrácia prekryvu: dva obvody si nárokujú rovnaký pás domov, prekryv je žltá šrafa"
                width={400}
                height={280}
                className="h-auto w-full"
              />
            </div>
            <figcaption className="space-y-1">
              <p className="text-sm font-semibold">2. Prekryv (Š2 FAIL)</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Žltá šrafa označuje plochu, kde si dve školy podľa VZN nárokujú
                rovnaké domy. Ide o priame porušenie § 44 Š2 — engine
                otvára critical finding a obvod je červený. Riešenie patrí
                samospráve: úprava VZN textu, nie portálu.
              </p>
            </figcaption>
          </figure>

          <figure className="rounded-lg border border-border bg-card p-3 space-y-2">
            <div className="relative aspect-[10/7] w-full overflow-hidden rounded-md bg-muted/30">
              <Image
                src="/methodology/example-island.svg"
                alt="Ilustrácia ostrova: malý fragment obvodu vzdialený od hlavnej plochy, ohraničený červenou prerušovanou čiarou"
                width={400}
                height={280}
                className="h-auto w-full"
              />
            </div>
            <figcaption className="space-y-1">
              <p className="text-sm font-semibold">3. Ostrov / možná segregácia</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Červenou prerušovanou čiarou je fragment obvodu odtrhnutý od
                hlavnej plochy. Pri kríži s Atlasom MRK vzniká RISK na Š3 —
                ostrov môže oddeľovať skupinu detí mimo zvyšku obvodu.
                Engine to neoznačuje za FAIL, ale za <em>unresolved anomaly</em> na manuálne preskúmanie.
              </p>
            </figcaption>
          </figure>
        </div>

        <p className="text-xs text-muted-foreground mt-3 not-prose">
          Reálne screenshoty z portálu pribudnú po nasadení demo dát — ilustrácie vyššie
          zodpovedajú tomu, čo na mape vidno pri rovnakej kombinácii vrstiev.
        </p>
      </section>

      {/* Section 4: do / don't */}
      <section id="co-robime" className="scroll-mt-20">
        <h2 className="text-lg font-semibold mb-1 not-prose">Čo robíme, čo nerobíme</h2>
        <p className="text-sm text-muted-foreground mb-4 not-prose">
          Transparentne — kde je hranica portálu. Cieľ je identifikovať problémy v VZN
          textoch a podklad pre rozhodnutie samosprávy, nie samospráve rozhodovať.
        </p>

        <div className="not-prose grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-green-200 bg-green-50/40 p-4">
            <p className="text-sm font-semibold text-green-900 mb-2">Čo robíme</p>
            <ul className="space-y-1.5 text-xs text-green-950/90 list-disc list-inside leading-relaxed">
              <li>Scrape VZN textu z mestských webov (pilot Prešov)</li>
              <li>Geokódovanie ulíc a domov cez Google Maps API</li>
              <li>Voronoi tessellation pre rekonštrukciu polygónov obvodov</li>
              <li>Detekcia prekryvov, ostrovov a možnej segregácie</li>
              <li>Vyhodnocovanie § 44 zákona 321 (Š1–Š4 a Pa–Pb)</li>
              <li>Pracujeme len s verejne dostupnými dátami, bez osobných údajov</li>
            </ul>
          </div>

          <div className="rounded-lg border border-red-200 bg-red-50/40 p-4">
            <p className="text-sm font-semibold text-red-900 mb-2">Čo nerobíme</p>
            <ul className="space-y-1.5 text-xs text-red-950/90 list-disc list-inside leading-relaxed">
              <li>Real-time prístup do Registra adries MŠSR — čaká na sprístupnenie</li>
              <li>Kapacitu budov ZŠ z EDUZBER zatiaľ neberieme (INSUFFICIENT_DATA)</li>
              <li>Účet jednotlivých detí — osobné údaje mimo GDPR</li>
              <li>Nerozhodujeme za samosprávu — len identifikujeme problémy v VZN</li>
              <li>Nenahrádzame VZN — sme nástroj na kontrolu, nie zdroj práva</li>
              <li>Nepoužívame ML ani jazykové modely na verdikt — len deterministickú logiku</li>
            </ul>
          </div>
        </div>

        <p className="text-xs text-muted-foreground mt-3 not-prose">
          Akýkoľvek nález portálu je <strong>podklad na overenie</strong>, nie záväzný
          výrok. Konečné rozhodnutie patrí samospráve a štátnemu školskému dozoru.
        </p>
      </section>

      {/* ===== /Sprint M-4 ===== */}

      <section id="verzie" className="scroll-mt-20">
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
