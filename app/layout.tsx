import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { cn } from "@/lib/utils";
import { AppHeader } from "@/components/layout/app-header";
import { AppNav } from "@/components/layout/app-nav";
import { EngineFooter } from "@/components/engine-footer";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "Kontrola § 44 — Školské obvody",
  description:
    "Analytický portál pre kontrolu verejných školských obvodov podľa § 44 zákona č. 321/2025 Z. z.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="sk" className={cn(geistSans.variable, geistMono.variable)}>
      <body className="antialiased min-h-screen flex flex-col bg-background text-foreground">
        {/* Skip link — WCAG 2.4.1 */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:rounded focus:bg-primary focus:text-primary-foreground focus:text-sm"
        >
          Preskočiť na hlavný obsah
        </a>
        <AppHeader />
        <div className="flex flex-1">
          <AppNav />
          <main id="main-content" className="flex-1 p-6 overflow-auto">
            {children}
          </main>
        </div>
        <EngineFooter />
      </body>
    </html>
  );
}
