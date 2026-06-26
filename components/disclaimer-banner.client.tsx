'use client'

import { useState, useEffect } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

type Props = {
  alwaysShow: boolean
  methodologyVersion: string
  engineVersion: string
}

const DISMISS_KEY = 'dismiss_disclaimer_session'

export function DisclaimerBannerClient({ alwaysShow, methodologyVersion, engineVersion }: Props) {
  const [dismissed, setDismissed] = useState(false)
  const [hidden, setHidden] = useState(false)

  useEffect(() => {
    if (!alwaysShow) {
      try {
        if (localStorage.getItem(DISMISS_KEY) === '1') {
          setDismissed(true)
        }
      } catch {
        // localStorage not available (SSR edge case)
      }
    }
  }, [alwaysShow])

  if (dismissed || hidden) return null

  function handleDismiss() {
    try {
      localStorage.setItem(DISMISS_KEY, '1')
    } catch {
      // ignore
    }
    setHidden(true)
  }

  return (
    <Alert
      role="note"
      aria-label="Upozornenie — toto je demo analytický výstup, nie oficiálny právny výklad"
      className="mb-4 border-amber-300 bg-amber-50 text-amber-900"
    >
      <AlertTitle className="font-semibold">Demo — nie oficiálny výklad</AlertTitle>
      <AlertDescription className="mt-1 text-sm">
        Toto demo zobrazuje analytické výstupy nad verejne dostupnými dátami pre 12 školských
        obvodov mesta Prešov.{' '}
        <strong>Nie je oficiálnym výkladom súladu so § 44 zákona č. 596/2003.</strong> Hodnoty{' '}
        <code className="rounded bg-amber-100 px-1 font-mono text-xs">INCOMPLETE</code> /{' '}
        <code className="rounded bg-amber-100 px-1 font-mono text-xs">INSUFFICIENT_DATA</code>{' '}
        znamenajú <strong>chýbajúce dáta</strong>, nie porušenie. Verzia metodiky:{' '}
        <code className="font-mono text-xs">{methodologyVersion}</code>. Verzia enginu:{' '}
        <code className="font-mono text-xs">{engineVersion}</code>.
      </AlertDescription>
      {!alwaysShow && (
        <button
          onClick={handleDismiss}
          className="mt-2 text-xs underline text-amber-800 hover:text-amber-900"
          aria-label="Zatvoriť upozornenie na túto návštevu"
        >
          Zatvoriť na túto návštevu
        </button>
      )}
    </Alert>
  )
}
