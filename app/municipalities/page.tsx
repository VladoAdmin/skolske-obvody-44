export const metadata = { title: "Zriaďovatelia — Kontrola § 44" };

/** Sprint 4: compliance scorecard per municipality/founder */
export default function MunicipalitiesPage() {
  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">Zriaďovatelia</h1>
      <p className="text-sm text-muted-foreground">
        Compliance scorecard per obec / zriaďovateľ. Pilot: Prešov + 3 obce.
        Semafor (Š1–Š3 + P-a–P-d): Sprint 2–3.
      </p>
      <div className="rounded border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        Implementácia: Sprint 2–4 (po dátovej vrstve a engine)
      </div>
    </div>
  );
}
