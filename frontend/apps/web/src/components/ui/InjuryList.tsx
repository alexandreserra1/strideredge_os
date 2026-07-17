import { useMemo } from 'react'
import type { InjuryReport, InjuryTaxonomy } from '@strideredge/core'
import { REGION_LABELS, SIDE_LABELS, severityBand } from './injuryCopy'

interface InjuryListProps {
  reports: InjuryReport[]
  taxonomy: InjuryTaxonomy | null
}

interface Group {
  key: string
  regionLabel: string
  sideLabel: string
  reports: InjuryReport[]   // do mais recente pro mais antigo
}

// Agrupa por REGIÃO+lado (o reframe: a região é a verdade estruturada; o atleta não auto-diagnostica).
// Log append-only → evolução de severidade visível por grupo.
function groupReports(reports: InjuryReport[], _taxonomy: InjuryTaxonomy | null): Group[] {
  const groups = new Map<string, Group>()
  for (const r of reports) {
    const key = `${r.region}|${r.side}`
    const g = groups.get(key) ?? {
      key,
      regionLabel: r.region ? REGION_LABELS[r.region] ?? r.region : '—',
      sideLabel: r.side ? SIDE_LABELS[r.side] ?? r.side : '',
      reports: [],
    }
    g.reports.push(r)
    groups.set(key, g)
  }
  return [...groups.values()]
}

export default function InjuryList({ reports, taxonomy }: InjuryListProps) {
  const groups = useMemo(() => groupReports(reports, taxonomy), [reports, taxonomy])

  if (reports.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border-light p-8 text-center">
        <p className="text-sm text-text-secondary">
          Nenhuma lesão registrada ainda. Registrar suas lesões alimenta a análise de risco ao longo do tempo.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {groups.map((g) => {
        const latest = g.reports[0]
        const band = severityBand(latest.severity)
        return (
          <div key={g.key} className="rounded-2xl border border-border-light bg-surface-100 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-text-primary">
                  {g.regionLabel}{g.sideLabel && <span className="text-text-secondary font-normal"> · {g.sideLabel}</span>}
                </p>
                {latest.symptom_text && (
                  <p className="text-xs text-text-secondary italic">"{latest.symptom_text}"</p>
                )}
              </div>
              <div className="text-right shrink-0">
                <p className={`text-sm font-bold ${band.tone}`}>{band.label}</p>
                <p className="text-[10px] text-text-secondary">severidade {latest.severity}/100</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border-light pt-3">
              {g.reports.map((r) => {
                const b = severityBand(r.severity)
                return (
                  <span key={r.id}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-surface-200 px-2 py-1 text-[11px]">
                    <span className="text-text-secondary">{r.onset_date ?? r.reported_at.slice(0, 10)}</span>
                    <span className={`font-semibold ${b.tone}`}>{r.severity}</span>
                  </span>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
