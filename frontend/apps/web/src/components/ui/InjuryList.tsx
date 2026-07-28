import { useMemo, useState, useCallback } from 'react'
import { AlertTriangle, Check, Loader2, Sparkles } from 'lucide-react'
import { api } from '@strideredge/core'
import type { InjuryReport, InjuryTaxonomy, InjuryRetrospective } from '@strideredge/core'
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
      {groups.map((g) => <InjuryGroupCard key={g.key} group={g} />)}
    </div>
  )
}

// Um grupo região+lado: o histórico de severidade + o RETROSPECTO (cruza a lesão com os sinais
// biomecânicos que a literatura liga a ela, nas análises de forma ANTES do onset).
function InjuryGroupCard({ group: g }: { group: Group }) {
  const latest = g.reports[0]
  const band = severityBand(latest.severity)
  const [retro, setRetro] = useState<InjuryRetrospective | null>(null)
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try { setRetro(await api.injuries.retrospective(latest.id)) }
    catch { setRetro(null) }
    finally { setLoading(false) }
  }, [latest.id])

  return (
    <div className="rounded-2xl border border-border-light bg-surface-100 p-4">
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

      {/* Retrospecto — só faz sentido quando há um diagnóstico pra cruzar */}
      {!retro && (
        <button onClick={load} disabled={loading}
          className="mt-3 btn-ghost text-xs flex items-center gap-1.5">
          {loading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} className="text-brand" />}
          {loading ? 'Cruzando com sua forma…' : 'O que minhas análises mostravam antes?'}
        </button>
      )}
      {retro && <Retrospective retro={retro} />}
    </div>
  )
}

function Retrospective({ retro }: { retro: InjuryRetrospective }) {
  return (
    <div className="mt-3 rounded-xl bg-brand/[0.04] border border-brand/15 p-3 animate-fade-in">
      {retro.status === 'ok' ? (
        <>
          <p className="text-[11px] text-text-secondary mb-2">
            Sinais que a ciência liga a <span className="font-medium">{retro.diagnosis_label}</span>,
            nas suas {retro.analyses_before} análise(s) das ~{retro.window_weeks} semanas antes:
          </p>
          <ul className="space-y-1.5">
            {retro.signals.map((s) => (
              <li key={s.metric} className="flex items-start gap-2 text-xs">
                {s.present === true
                  ? <AlertTriangle size={13} className="text-accent-yellow shrink-0 mt-0.5" />
                  : s.present === false
                  ? <Check size={13} className="text-accent-green shrink-0 mt-0.5" />
                  : <span className="text-text-muted shrink-0 text-[13px] leading-none mt-0.5">–</span>}
                <span className="text-text-primary">
                  {s.label}
                  {s.present === true && <span className="text-accent-yellow"> — aparecia ({s.value}{s.unit}, ideal {s.ideal})</span>}
                  {s.present === false && <span className="text-text-secondary"> — estava na faixa ideal</span>}
                  {s.present === null && <span className="text-text-muted"> — {s.note}</span>}
                </span>
              </li>
            ))}
          </ul>
          {retro.source && <p className="text-[10px] text-text-muted mt-2" title={retro.source}>📚 {retro.source}</p>}
        </>
      ) : (
        <p className="text-[11px] text-text-secondary">{retro.caveat}</p>
      )}
      {retro.status === 'ok' && (
        <p className="text-[10px] text-text-muted mt-2 leading-snug">{retro.caveat}</p>
      )}
    </div>
  )
}
