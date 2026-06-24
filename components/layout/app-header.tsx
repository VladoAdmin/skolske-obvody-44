import Link from "next/link";

/**
 * Application header — ID-SK-inspired, sober government style.
 * Provides the top bar with branding and top-level identity.
 */
export function AppHeader() {
  return (
    <header className="border-b border-border bg-background" role="banner">
      <div className="flex items-center justify-between px-6 py-3">
        <Link
          href="/"
          className="flex items-center gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
          aria-label="Kontrola § 44 — domov"
        >
          {/* ID-SK style: minimal wordmark, no decorative logo */}
          <span className="font-semibold text-sm tracking-tight">
            Kontrola § 44
          </span>
          <span
            aria-hidden="true"
            className="text-xs text-muted-foreground border border-border rounded px-1.5 py-0.5 font-mono"
          >
            PSK pilot
          </span>
        </Link>

        <div className="flex items-center gap-4">
          <span className="text-xs text-muted-foreground hidden sm:block">
            Zákon č. 321/2025 Z. z., § 44
          </span>
          {/* Sprint 5: auth nav goes here */}
          <span className="text-xs text-muted-foreground border border-dashed border-border rounded px-2 py-1">
            Prihlásenie (Sprint 5)
          </span>
        </div>
      </div>
    </header>
  );
}
