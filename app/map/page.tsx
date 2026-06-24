import { Suspense } from "react";
import { MapPlaceholder } from "@/components/map/map-placeholder";
import { MapClient } from "@/components/map/map-client";

export const metadata = {
  title: "Mapa PSK — Kontrola § 44",
};

/**
 * Map page — PSK overview.
 * MapClient is lazy-loaded (client component) because MapLibre needs browser APIs.
 * MapPlaceholder is the accessible skeleton shown during load.
 *
 * ID-SK requirement: every map MUST have a table equivalent toggle.
 * The table toggle is wired in Sprint 4; the toggle button is stubbed here.
 */
export default function MapPage() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Mapa PSK</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Prehľad školských obvodov — Prešovský samosprávny kraj
          </p>
        </div>
        {/* ID-SK: map ↔ table toggle — wired in Sprint 4 */}
        <button
          type="button"
          aria-label="Prepnúť na tabuľkový výstup (Sprint 4)"
          disabled
          className="text-xs border border-dashed border-border rounded px-3 py-1.5 text-muted-foreground cursor-not-allowed"
        >
          Tabuľkový výstup (Sprint 4)
        </button>
      </div>

      <div
        className="rounded-lg border border-border overflow-hidden"
        style={{ height: "60vh", minHeight: 400 }}
      >
        <Suspense fallback={<MapPlaceholder />}>
          <MapClient />
        </Suspense>
      </div>

      <p className="text-xs text-muted-foreground">
        Podkladová mapa: OpenStreetMap contributors. Dátové vrstvy (obvody, školy,
        MRK) sa načítajú v Sprinte 1. Verdikty (semafor) v Sprinte 2.
      </p>
    </div>
  );
}
