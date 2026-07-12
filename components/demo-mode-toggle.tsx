'use client'

import { useDemoMode } from '@/lib/demo-mode/context'

// VLA-34: single global switch, rendered once in the app header (present on
// every page — map, findings register, district detail). ON (checked) =
// current default behaviour (DEMO scenarios visible); OFF = real-only.
export function DemoModeToggle() {
  const { demoMode, setDemoMode } = useDemoMode()

  return (
    <button
      type="button"
      role="switch"
      aria-checked={demoMode}
      data-testid="demo-mode-toggle"
      onClick={() => setDemoMode(!demoMode)}
      title={
        demoMode
          ? 'Zobrazené: reálne dáta + DEMO scenáre. Kliknutím prepnete na len reálne dáta.'
          : 'Zobrazené: len reálne dáta. Kliknutím zapnete DEMO scenáre.'
      }
      className={[
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        demoMode
          ? 'border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100'
          : 'border-emerald-300 bg-emerald-50 text-emerald-900 hover:bg-emerald-100',
      ].join(' ')}
    >
      <span
        aria-hidden="true"
        className={[
          'relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors',
          demoMode ? 'bg-amber-400' : 'bg-emerald-500',
        ].join(' ')}
      >
        <span
          className={[
            'inline-block h-3 w-3 translate-x-0.5 transform rounded-full bg-white shadow transition-transform',
            demoMode ? 'translate-x-3.5' : 'translate-x-0.5',
          ].join(' ')}
        />
      </span>
      <span className="whitespace-nowrap">
        {demoMode ? 'DEMO režim' : 'Len reálne dáta'}
      </span>
    </button>
  )
}
