"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "/", label: "Prehľad" },
  { href: "/map", label: "Mapa PSK" },
  { href: "/municipalities", label: "Zriaďovatelia" },
  { href: "/findings", label: "Register nálezov" },
  { href: "/o-metodike", label: "O metodike" },
  { href: "/admin", label: "Správa dát" },
] as const;

/**
 * Sidebar navigation — analyst-first layout, keyboard accessible.
 */
export function AppNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Hlavná navigácia"
      className="w-52 flex-shrink-0 border-r border-border py-4 hidden md:block"
    >
      <ul className="space-y-0.5 px-2 list-none m-0 p-0">
        {NAV_LINKS.map((link) => {
          const isActive =
            link.href === "/"
              ? pathname === "/"
              : pathname.startsWith(link.href);
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "block rounded px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isActive
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                )}
              >
                {link.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
