"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

interface MapWithPanelProps {
  mapSlot: React.ReactNode;
  panelSlot: React.ReactNode;
  findingsCount: number;
}

/**
 * Responsive wrapper for the map + findings panel layout.
 * Mobile (< md): stacked, with Mapa / Nálezy tab switcher.
 * Tablet (md–lg): flex-row, panel w-72, height 60vh.
 * Desktop (>= lg): flex-row, panel w-80, height 60vh.
 */
export function MapWithPanel({ mapSlot, panelSlot, findingsCount }: MapWithPanelProps) {
  const [activeTab, setActiveTab] = useState<"map" | "list">("map");

  return (
    <>
      {/* Mobile tab switcher — only on < md */}
      <div className="flex md:hidden border border-border rounded-lg overflow-hidden mb-2">
        <button
          onClick={() => setActiveTab("map")}
          aria-pressed={activeTab === "map"}
          className={cn(
            "flex-1 py-2 text-sm font-medium transition-colors",
            activeTab === "map"
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:bg-accent/50"
          )}
        >
          Mapa
        </button>
        <button
          onClick={() => setActiveTab("list")}
          aria-pressed={activeTab === "list"}
          className={cn(
            "flex-1 py-2 text-sm font-medium transition-colors border-l border-border",
            activeTab === "list"
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:bg-accent/50"
          )}
        >
          Nálezy{findingsCount > 0 ? ` (${findingsCount})` : ""}
        </button>
      </div>

      {/* Layout wrapper */}
      <div className="flex flex-col md:flex-row gap-4">
        {/* Map container */}
        <div
          className={cn(
            "flex-1 rounded-lg border border-border overflow-hidden",
            // Mobile: show only when map tab active; height 50vh
            "md:block",
            activeTab === "map" ? "block" : "hidden md:block"
          )}
          style={{ height: undefined }}
        >
          <div className="h-[65vh] md:h-[60vh] min-h-[320px]">
            {mapSlot}
          </div>
        </div>

        {/* Findings panel */}
        <div
          className={cn(
            "rounded-lg border border-border overflow-hidden flex-shrink-0",
            // Mobile: full-width, show only when list tab active
            "w-full md:w-72 lg:w-80",
            "md:block",
            activeTab === "list" ? "block" : "hidden md:block"
          )}
          style={{ height: undefined }}
        >
          <div className="h-[65vh] md:h-[60vh] min-h-[320px]">
            {panelSlot}
          </div>
        </div>
      </div>
    </>
  );
}
