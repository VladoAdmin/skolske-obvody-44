'use client'

import { useState, useEffect } from 'react'

type Props = {
  methodologyVersion: string
  engineVersion: string
}

// First-load modal: shown once per browser (localStorage). The slim top banner
// is always present so the DEMO nature stays visible without blocking content.
const POPUP_SEEN_KEY = 'demo_popup_seen_v1'

/**
 * Single app-wide DEMO disclaimer (item 17). Replaces the per-page banners and
 * the scattered inline disclaimer prose with:
 *   1. a slim, always-visible top banner, and
 *   2. a dismissible first-load popup (once per browser).
 * Per-value DEMO provenance chips elsewhere are intentionally kept (mock-data
 * invariant — mock values must stay visibly flagged).
 */
export function DisclaimerBannerClient({ methodologyVersion, engineVersion }: Props) {
  const [showPopup, setShowPopup] = useState(false)

  useEffect(() => {
    try {
      if (localStorage.getItem(POPUP_SEEN_KEY) !== '1') {
        setShowPopup(true)
      }
    } catch {
      // localStorage unavailable — skip the popup, keep the banner.
    }
  }, [])

  function dismissPopup() {
    try {
      localStorage.setItem(POPUP_SEEN_KEY, '1')
    } catch {
      // ignore
    }
    setShowPopup(false)
  }

  return (
    <>
      {/* Slim, always-on banner — the single page-level DEMO notice. */}
      <div
        role="note"
        aria-label="Demo ukážka funkcionalít — záver nie je záväzný"
        className="flex items-center gap-2 border-b border-amber-300 bg-amber-50 px-4 py-1.5 text-xs text-amber-900 md:px-6"
      >
        <span
          className="inline-flex shrink-0 items-center rounded-sm bg-amber-200 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-900"
          aria-hidden="true"
        >
          Demo
        </span>
        <span className="font-medium">
          DEMO ukážka funkcionalít — záver nie je záväzný.
        </span>
      </div>

      {/* First-load popup (once per browser). */}
      {showPopup && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="demo-popup-title"
          className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 p-4"
          onClick={dismissPopup}
        >
          <div
            className="max-w-md rounded-lg border border-gov-border bg-white p-6 shadow-gov-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="demo-popup-title" className="text-card font-semibold text-gov-blue">
              DEMO ukážka funkcionalít
            </h2>
            <p className="mt-2 text-sm text-gov-ink">
              Tento portál zobrazuje analytické výstupy nad verejne dostupnými dátami pre 12
              školských obvodov mesta Prešov.{' '}
              <strong>
                Nie je oficiálnym výkladom súladu so § 44 zákona č. 596/2003 — záver nie je
                záväzný.
              </strong>
            </p>
            <p className="mt-2 text-sm text-gov-muted">
              Časť hodnôt je ukážková (vyplnenie dátových medzier) a nevstupuje do zákonného
              verdiktu; slúžia na demonštráciu funkcionality.
            </p>
            <p className="mt-2 text-xs text-gov-muted">
              Verzia metodiky: <code className="font-mono">{methodologyVersion}</code> · Verzia
              enginu: <code className="font-mono">{engineVersion}</code>
            </p>
            <button
              onClick={dismissPopup}
              className="mt-4 rounded-sm bg-gov-blue px-4 py-1.5 text-sm font-medium text-white hover:bg-gov-blue/90"
            >
              Rozumiem
            </button>
          </div>
        </div>
      )}
    </>
  )
}
