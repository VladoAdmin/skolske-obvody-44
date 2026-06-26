'use client'

import { useState } from 'react'
import type { DistrictMapFeature } from '@/lib/supabase/types'
import { getDistrictHue } from '@/lib/config/region'
import {
  EVENT_SELECT_DISTRICT,
  EVENT_TOGGLE_DISTRICT,
  type SelectDistrictDetail,
  type ToggleDistrictDetail,
} from '@/lib/map-events'

interface DistrictTogglePanelProps {
  features: DistrictMapFeature[]
}

export function DistrictTogglePanel({ features }: DistrictTogglePanelProps) {
  const [open, setOpen] = useState(true)
  const [enabledIds, setEnabledIds] = useState<Set<string>>(() => new Set(features.map((f) => f.id)))
  const [selectedId, setSelectedId] = useState<string | null>(null)

  function toggleDistrict(id: string) {
    setEnabledIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      window.dispatchEvent(new CustomEvent<ToggleDistrictDetail>(EVENT_TOGGLE_DISTRICT, { detail: { id, visible: next.has(id) } }))
      return next
    })
  }

  function selectDistrict(feature: DistrictMapFeature) {
    setSelectedId(feature.id)
    window.dispatchEvent(new CustomEvent<SelectDistrictDetail>(EVENT_SELECT_DISTRICT, { detail: { id: feature.id } }))
    // Also flyTo centroid if available
    // Districts don't have centroid on the feature directly — dispatch select-district and let map handle flyTo
  }

  function selectAll() {
    const all = new Set(features.map((f) => f.id))
    setEnabledIds(all)
    features.forEach((f) => {
      window.dispatchEvent(new CustomEvent<ToggleDistrictDetail>(EVENT_TOGGLE_DISTRICT, { detail: { id: f.id, visible: true } }))
    })
  }

  function selectNone() {
    setEnabledIds(new Set())
    features.forEach((f) => {
      window.dispatchEvent(new CustomEvent<ToggleDistrictDetail>(EVENT_TOGGLE_DISTRICT, { detail: { id: f.id, visible: false } }))
    })
  }

  if (features.length === 0) return null

  return (
    <div className="border-b border-border flex-shrink-0">
      {/* Header */}
      <button
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-foreground hover:bg-muted/50 transition-colors"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>Obvody ({features.length})</span>
        <span className="text-muted-foreground">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="flex flex-col">
          {/* List */}
          <ul className="max-h-48 overflow-y-auto">
            {features.map((f, index) => {
              const hue = getDistrictHue(index)
              const color = `hsl(${hue}, 65%, 45%)`
              const isEnabled = enabledIds.has(f.id)
              const isSelected = selectedId === f.id

              return (
                <li key={f.id} className={['flex items-center gap-2 px-3 py-1.5 text-xs border-b border-border/50 last:border-0', isSelected ? 'bg-muted' : 'hover:bg-muted/30'].join(' ')}>
                  {/* Checkbox toggle */}
                  <input
                    type="checkbox"
                    checked={isEnabled}
                    onChange={() => toggleDistrict(f.id)}
                    className="flex-shrink-0 cursor-pointer"
                    aria-label={`Zobraziť obvod ${f.name}`}
                  />
                  {/* Color chip */}
                  <span
                    className="flex-shrink-0 inline-block w-3 h-3 rounded-sm border"
                    style={{ background: color, borderColor: color, opacity: isEnabled ? 1 : 0.3 }}
                  />
                  {/* Name — click to select + flyTo */}
                  <button
                    className="flex-1 text-left truncate text-foreground hover:text-primary transition-colors"
                    onClick={() => selectDistrict(f)}
                    title={f.name}
                  >
                    {f.name}
                  </button>
                </li>
              )
            })}
          </ul>

          {/* Select all / none */}
          <div className="flex gap-2 px-3 py-2 border-t border-border/50">
            <button
              className="text-xs text-primary hover:underline"
              onClick={selectAll}
            >
              Vybrať všetky
            </button>
            <span className="text-muted-foreground">·</span>
            <button
              className="text-xs text-primary hover:underline"
              onClick={selectNone}
            >
              Žiadny
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
