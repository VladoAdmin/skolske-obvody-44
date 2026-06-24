export const metadata = { title: "Register nálezov — Kontrola § 44" };

/** Sprint 4: findings register with filters (severity, condition, status, data completeness) + export */
export default function FindingsPage() {
  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Register nálezov</h1>
      <p className="text-sm text-muted-foreground">
        Zoznam odchýlok a výnimiek per VZN. Filtre: závažnosť, podmienka, stav,
        úplnosť dát. Export: Sprint 4.
      </p>
      <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        Implementácia: Sprint 3–4 (po Sprinte 2 — engine § 44)
      </div>
    </div>
  );
}
