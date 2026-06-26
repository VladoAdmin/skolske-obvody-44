"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MenuIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SheetClose,
} from "@/components/ui/sheet";

const NAV_LINKS = [
  { href: "/", label: "Prehľad" },
  { href: "/map", label: "Mapa PSK" },
  { href: "/municipalities", label: "Zriaďovatelia" },
  { href: "/findings", label: "Register nálezov" },
  { href: "/o-metodike", label: "O metodike" },
  { href: "/admin", label: "Správa dát" },
] as const;

/**
 * Application header — ID-SK-inspired, sober government style.
 * Mobile (< md): hamburger button + Sheet drawer nav.
 * Desktop (>= md): static header, sidebar nav handles navigation.
 */
export function AppHeader() {
  const pathname = usePathname();

  return (
    <header className="border-b border-border bg-background" role="banner">
      <div className="flex items-center justify-between px-4 md:px-6 py-3">
        <div className="flex items-center gap-3">
          {/* Mobile hamburger — only visible on < md */}
          <Sheet>
            <SheetTrigger
              className="md:hidden inline-flex items-center justify-center h-8 w-8 rounded-md hover:bg-accent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="Otvoriť navigáciu"
            >
              <MenuIcon className="h-5 w-5" />
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <SheetHeader className="border-b border-border px-4 py-3">
                <SheetTitle className="text-sm font-semibold">
                  Kontrola § 44
                </SheetTitle>
              </SheetHeader>
              <nav aria-label="Mobilná navigácia" className="py-2">
                <ul className="space-y-0.5 px-2 list-none m-0">
                  {NAV_LINKS.map((link) => {
                    const isActive =
                      link.href === "/"
                        ? pathname === "/"
                        : pathname.startsWith(link.href);
                    return (
                      <li key={link.href}>
                        <SheetClose
                          render={
                            <Link
                              href={link.href}
                              aria-current={isActive ? "page" : undefined}
                              className={cn(
                                "block rounded px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                isActive
                                  ? "bg-accent font-medium text-accent-foreground"
                                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                              )}
                            />
                          }
                        >
                          {link.label}
                        </SheetClose>
                      </li>
                    );
                  })}
                </ul>
              </nav>
            </SheetContent>
          </Sheet>

          <Link
            href="/"
            className="flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
            aria-label="Kontrola § 44 — domov"
          >
            <span className="font-semibold text-sm tracking-tight">
              Kontrola § 44
            </span>
            <span
              aria-hidden="true"
              className="text-xs text-muted-foreground border border-border rounded px-1.5 py-0.5 font-mono hidden sm:inline"
            >
              PSK pilot
            </span>
          </Link>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-xs text-muted-foreground hidden lg:block">
            Zákon č. 321/2025 Z. z., § 44
          </span>
          {/* Sprint 5: auth nav — hidden on mobile to save space */}
          <span className="text-xs text-muted-foreground border border-dashed border-border rounded px-2 py-1 hidden md:inline-flex">
            Prihlásenie (Sprint 5)
          </span>
        </div>
      </div>
    </header>
  );
}
