export const metadata = { title: "Správa dát — Kontrola § 44" };

/** Sprint 5: admin console — staging → validation → publish workflow */
export default function AdminPage() {
  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Správa dát</h1>
      <p className="text-sm text-muted-foreground">
        Admin konzola: import datasetu (CSV/JSON/SHP/GeoJSON) so staging →
        validácia → publish workflow. Správa zdrojových URL. Plánovač.
        Implementácia: Sprint 5.
      </p>
      <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        Implementácia: Sprint 5 (vyžaduje auth — Sprint 5)
      </div>
    </div>
  );
}
