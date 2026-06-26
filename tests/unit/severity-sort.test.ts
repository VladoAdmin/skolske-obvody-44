import { describe, it, expect } from 'vitest'
import { SEVERITY_RANK, type Severity } from '@/lib/format/severity'

describe('severity-sort', () => {
  it('should have correct severity_rank ordering', () => {
    expect(SEVERITY_RANK.critical).toBe(5)
    expect(SEVERITY_RANK.high).toBe(4)
    expect(SEVERITY_RANK.medium).toBe(3)
    expect(SEVERITY_RANK.low).toBe(2)
    expect(SEVERITY_RANK.info).toBe(1)
  })

  it('should sort findings by severity_rank in descending order', () => {
    const findings = [
      { finding_id: '1', severity: 'info' as Severity, severity_rank: 1 },
      { finding_id: '2', severity: 'critical' as Severity, severity_rank: 5 },
      { finding_id: '3', severity: 'medium' as Severity, severity_rank: 3 },
      { finding_id: '4', severity: 'low' as Severity, severity_rank: 2 },
      { finding_id: '5', severity: 'high' as Severity, severity_rank: 4 },
    ]

    const sorted = [...findings].sort((a, b) => b.severity_rank - a.severity_rank)

    expect(sorted.map((f) => f.finding_id)).toEqual(['2', '5', '3', '4', '1'])
    expect(sorted[0].severity).toBe('critical')
    expect(sorted[sorted.length - 1].severity).toBe('info')
  })

  it('should maintain correct rank values for all severity levels', () => {
    const severities: Severity[] = ['critical', 'high', 'medium', 'low', 'info']
    const ranks = severities.map((s) => SEVERITY_RANK[s])
    expect(ranks).toEqual([5, 4, 3, 2, 1])
  })
})
