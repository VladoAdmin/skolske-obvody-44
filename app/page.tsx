import Link from "next/link";

export default function Home() {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <section aria-labelledby="portal-heading">
        <h1
          id="portal-heading"
          className="text-2xl font-semibold tracking-tight mb-2"
        >
          Kontrola § 44 — Školské obvody
        </h1>
        <p className="text-muted-foreground">
          Analytický portál pre referentov RÚŠS a ministerstva školstva. Portál
          overuje súlad verejných školských obvodov s § 44 zákona č. 321/2025
          Z. z. Pilot: Prešovský samosprávny kraj (PSK).
        </p>
      </section>

      <section aria-labelledby="quick-access-heading" className="space-y-4">
        <h2 id="quick-access-heading" className="text-lg font-medium">
          Rýchly prístup
        </h2>
        <nav aria-label="Hlavné sekcie portálu">
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 list-none p-0 m-0">
            {NAV_ITEMS.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="block rounded-lg border border-border p-4 hover:bg-accent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="block font-medium text-sm">
                    {item.label}
                  </span>
                  <span className="block text-xs text-muted-foreground mt-1">
                    {item.description}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </section>

      <section
        aria-labelledby="pilot-status-heading"
        className="rounded-lg border border-border p-4 bg-muted/30"
      >
        <h2
          id="pilot-status-heading"
          className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3"
        >
          Stav pilotu — Sprint 0 (infraštruktúra)
        </h2>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="font-medium">Dátové vrstvy</dt>
          <dd className="text-muted-foreground">čakajú na Sprint 1</dd>
          <dt className="font-medium">Engine § 44</dt>
          <dd className="text-muted-foreground">čaká na Sprint 2</dd>
          <dt className="font-medium">Mapa PSK</dt>
          <dd className="text-muted-foreground">
            <Link href="/map" className="underline hover:text-foreground">
              základný podklad aktívny
            </Link>
          </dd>
          <dt className="font-medium">DB schéma</dt>
          <dd className="text-muted-foreground">migrácie pripravené</dd>
        </dl>
      </section>
    </div>
  );
}

const NAV_ITEMS = [
  {
    href: "/map",
    label: "Mapa PSK",
    description: "Prehľad obvodov celého Prešovského kraja",
  },
  {
    href: "/findings",
    label: "Register nálezov",
    description: "Zoznam odchýlok a výnimiek per VZN",
  },
  {
    href: "/municipalities",
    label: "Zriaďovatelia",
    description: "Scorecard per obec / zriaďovateľ",
  },
  {
    href: "/admin",
    label: "Správa dát",
    description: "Import, validácia, kvalita zdrojov",
  },
] as const;
