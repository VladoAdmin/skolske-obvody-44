'use client'

import { useState } from 'react'
import type { SoFindingsPanelItem, DistrictMapFeature } from '@/lib/supabase/types'
import { DistrictTogglePanel } from '@/components/district-toggle-panel'

interface FindingsPanelProps {
  findings: SoFindingsPanelItem[]
  features?: DistrictMapFeature[]
}

type SeverityFilter = 'critical' | 'high' | 'medium'

const SEVERITY_LABELS: Record<SeverityFilter, string> = {
  critical: 'Kritická',
  high: 'Vysoká',
  medium: 'Stredná',
}

const SEVERITY_BADGE: Record<SeverityFilter, string> = {
  critical: 'bg-red-100 text-red-800 border border-red-300',
  high: 'bg-orange-100 text-orange-800 border border-orange-300',
  medium: 'bg-yellow-100 text-yellow-800 border border-yellow-300',
}

const ALL_SEVERITIES: SeverityFilter[] = ['critical', 'high', 'medium']

export function FindingsPanel({ findings, features = [] }: FindingsPanelProps) {
  const [activeFilters, setActiveFilters] = useState<Set<SeverityFilter>>(
    new Set(ALL_SEVERITIES)
  )
  const [selectedId, setSelectedId] = useState<string | null>(null)

  function toggleFilter(severity: SeverityFilter) {
    setActiveFilters((prev) => {
      const next = new Set(prev)
      if (next.has(severity)) {
        if (next.size === 1) return prev // keep at least one active
        next.delete(severity)
      } else {
        next.add(severity)
      }
      return next
    })
  }

  // Condition codes that represent distance/route findings (Pa = air-line ≤2km,
  // Pb = walking route). All others are boundary/composition findings.
  const DISTANCE_CODES = new Set(['Pa', 'Pb', 'Pc', 'Pd'])

  function handleItemClick(item: SoFindingsPanelItem) {
    setSelectedId(item.finding_id)

    const hasCentroid =
      typeof item.district_geom_centroid_lat === 'number' &&
      typeof item.district_geom_centroid_lon === 'number'

    if (hasCentroid) {
      window.dispatchEvent(
        new CustomEvent('so:flyto', {
          detail: {
            lat: item.district_geom_centroid_lat,
            lon: item.district_geom_centroid_lon,
            zoom: 14,
          },
        })
      )
    }

    const isDistanceFinding = DISTANCE_CODES.has(item.condition_code)

    if (isDistanceFinding) {
      // Draw a line from district centroid → school location to show the
      // problematic distance visually. School coords come from features prop.
      const feature = features.find((f) => f.id === item.district_id)
      const schoolGeom = feature?.school_geom_geojson as { type?: string; coordinates?: [number, number] } | null
      if (
        hasCentroid &&
        schoolGeom?.type === 'Point' &&
        Array.isArray(schoolGeom.coordinates)
      ) {
        const [schoolLon, schoolLat] = schoolGeom.coordinates
        window.dispatchEvent(
          new CustomEvent('so:draw-route', {
            detail: {
              districtId: item.district_id,
              from: {
                lat: item.district_geom_centroid_lat as number,
                lon: item.district_geom_centroid_lon as number,
              },
              to: { lat: schoolLat, lon: schoolLon },
              label: item.condition_label_sk,
            },
          })
        )
      }
    } else {
      // Boundary/composition finding — highlight the district polygon.
      window.dispatchEvent(
        new CustomEvent('so:select-district', {
          detail: { id: item.district_id },
        })
      )
    }
  }

  const filtered = findings
    .filter((f) => activeFilters.has(f.severity as SeverityFilter))
    // Sprint M-3: demo findings sort to the top; within each group keep
    // severity_rank ascending (critical first). Stable for findings without
    // is_demo because Array#sort in modern engines is stable.
    .slice()
    .sort((a, b) => {
      const aDemo = a.is_demo ? 0 : 1
      const bDemo = b.is_demo ? 0 : 1
      if (aDemo !== bDemo) return aDemo - bDemo
      // severity_rank is highest (5) for critical and lowest (1) for info,
      // so we sort descending to put critical first.
      return (b.severity_rank ?? 0) - (a.severity_rank ?? 0)
    })

  return (
    <div className="flex flex-col h-full bg-background">
      {/* District toggle panel — collapsible above findings */}
      {features.length > 0 && <DistrictTogglePanel features={features} />}

      {/* Header */}
      <div className="px-3 py-2 border-b border-border flex-shrink-0">
        <p className="text-xs font-semibold text-foreground">Nálezy</p>
        <p className="text-xs text-muted-foreground">{filtered.length} zobrazených</p>
      </div>

      {/* Severity filter toggles */}
      <div className="px-3 py-2 border-b border-border flex gap-1 flex-wrap flex-shrink-0">
        {ALL_SEVERITIES.map((sev) => (
          <button
            key={sev}
            onClick={() => toggleFilter(sev)}
            className={[
              'text-xs px-2 py-0.5 rounded-full border font-medium transition-opacity',
              SEVERITY_BADGE[sev],
              activeFilters.has(sev) ? 'opacity-100' : 'opacity-40',
            ].join(' ')}
            aria-pressed={activeFilters.has(sev)}
          >
            {SEVERITY_LABELS[sev]}
          </button>
        ))}
      </div>

      {/* Findings list */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <p className="text-xs text-muted-foreground p-3">Žiadne nálezy pre vybrané filtre.</p>
        ) : (
          <ul>
            {filtered.map((item) => (
              <li key={item.finding_id}>
                <button
                  onClick={() => handleItemClick(item)}
                  className={[
                    'w-full text-left px-3 py-2 border-b border-border text-xs',
                    'hover:bg-muted/50 transition-colors',
                    selectedId === item.finding_id ? 'bg-muted' : '',
                  ].join(' ')}
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={[
                        'mt-0.5 flex-shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold',
                        SEVERITY_BADGE[item.severity as SeverityFilter] ?? 'bg-muted text-muted-foreground',
                      ].join(' ')}
                    >
                      {SEVERITY_LABELS[item.severity as SeverityFilter] ?? item.severity}
                    </span>
                    {item.is_demo && (
                      <span
                        className="mt-0.5 flex-shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-600 text-white"
                        title="Ukážková chyba — demonštrácia toho, čo engine vie detegovať"
                      >
                        DEMO
                      </span>
                    )}
                    <div className="min-w-0">
                      <p className="font-medium text-foreground truncate">{item.district_name}</p>
                      <p className="text-muted-foreground truncate">{item.condition_label_sk}</p>
                      {item.evidence_public_text && (
                        <p className="text-muted-foreground mt-0.5 line-clamp-2">
                          {item.evidence_public_text}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
