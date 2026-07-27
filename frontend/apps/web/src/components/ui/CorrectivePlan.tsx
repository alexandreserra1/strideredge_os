import { useCallback, useState } from 'react'
import { CalendarRange, Info, Loader2, Sparkles } from 'lucide-react'
import { api } from '@strideredge/core'
import type { PlanResponse, PlanPhase } from '@strideredge/core'
import InfoHint from './InfoHint'

const WEEK_OPTIONS = [4, 6, 8, 12] as const

/**
 * Bloco de PLANO CORRETIVO de N semanas. Puxa `api.form.plan(id, weeks)` — plano faseado,
 * determinístico e citado. Trata captura ruim (`unreliable`): mostra só o aviso de refilmar.
 */
export default function CorrectivePlan({ analysisId }: { analysisId: string }) {
  const [weeks, setWeeks] = useState<number>(6)
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const generate = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setPlan(await api.form.plan(analysisId, weeks))
    } catch {
      setError('Não consegui montar o plano — o coach local está no ar?')
    } finally {
      setLoading(false)
    }
  }, [analysisId, weeks])

  return (
    <div className="mt-4 pt-4 border-t border-border-light">
      <h4 className="text-sm font-semibold flex items-center gap-1.5 mb-3">
        <CalendarRange size={15} className="text-brand" /> Plano corretivo de várias semanas
        <InfoHint text="Um programa faseado (ativar → fortalecer → treinar o gesto na corrida) que ataca seus desvios em ordem de risco. Cada exercício vem com a fonte citada. Sobe ~10% por semana." />
      </h4>

      {/* Seletor de duração + botão gerar */}
      {!plan?.unreliable && (
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className="text-[11px] text-text-secondary">Duração:</span>
          {WEEK_OPTIONS.map(w => (
            <button key={w} onClick={() => setWeeks(w)}
              className={`text-xs rounded-full border px-3 py-1 transition-colors ${
                weeks === w ? 'border-brand bg-brand/10 text-brand font-semibold'
                            : 'border-border-light text-text-secondary hover:border-border-medium'
              }`}>
              {w} sem
            </button>
          ))}
        </div>
      )}

      {!plan && (
        <button onClick={generate} disabled={loading} className="btn-primary text-sm w-full">
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 size={15} className="animate-spin" /> Montando seu plano de {weeks} semanas…
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <Sparkles size={15} /> Gerar plano de {weeks} semanas
            </span>
          )}
        </button>
      )}

      {error && <p className="text-xs text-accent-red mt-2">{error}</p>}

      {/* Captura ruim: sem plano, só o aviso de refilmar */}
      {plan?.unreliable && (
        <div className="rounded-xl bg-accent-yellow/10 border border-accent-yellow/25 p-4 animate-fade-in">
          <p className="text-xs font-semibold text-accent-yellow flex items-center gap-1.5">
            <Info size={14} /> Ainda não dá pra montar um plano honesto
          </p>
          <p className="text-[11px] text-text-secondary mt-1 leading-snug">{plan.caveat}</p>
          <button onClick={() => setPlan(null)} className="btn-ghost text-xs mt-3">
            Tentar de novo
          </button>
        </div>
      )}

      {/* Plano gerado */}
      {plan && !plan.unreliable && (
        <div className="space-y-4 animate-fade-in">
          {plan.intro && (
            <p className="text-sm text-text-secondary leading-relaxed">{plan.intro}</p>
          )}

          {/* Prioridades — o que o plano ataca primeiro */}
          {(plan.priority?.length ?? 0) > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] text-text-muted">Foco, do mais urgente:</span>
              {(plan.priority ?? []).map((p, i) => (
                <span key={p.metric}
                  className="text-[10px] text-brand bg-brand/10 border border-brand/20 px-2 py-0.5 rounded-full">
                  {i + 1}. {p.label}
                </span>
              ))}
            </div>
          )}

          {(plan.phases?.length ?? 0) === 0 && (
            <p className="text-sm text-text-secondary leading-relaxed">{plan.caveat}</p>
          )}

          {(plan.phases ?? []).map((ph, i) => <PhaseCard key={ph.key} phase={ph} step={i + 1} />)}

          {/* Caveat de honestidade em destaque */}
          {(plan.phases?.length ?? 0) > 0 && (
            <div className="rounded-xl bg-accent-yellow/10 border border-accent-yellow/25 p-3">
              <p className="text-[11px] text-text-secondary leading-snug flex items-start gap-1.5">
                <Info size={13} className="text-accent-yellow shrink-0 mt-0.5" />
                <span>{plan.caveat}</span>
              </p>
            </div>
          )}

          <button onClick={() => setPlan(null)} className="btn-ghost text-xs">
            Gerar outro plano
          </button>
        </div>
      )}
    </div>
  )
}

// Uma FASE do plano: passo (1/2/3), título, janela de semanas, o PORQUÊ da fase, e os exercícios
// (cada um UMA vez, com 'como fazer' + progressão + fonte). Sem repetir semana a semana.
function PhaseCard({ phase, step }: { phase: PlanPhase; step: number }) {
  return (
    <div className="rounded-xl border border-border-light bg-surface-200 p-3.5">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-brand text-white text-[10px] font-bold shrink-0">{step}</span>
        <span className="text-sm font-bold text-text-primary">{phase.title}</span>
        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-brand/12 text-brand ml-auto whitespace-nowrap">
          {phase.weeks_label}
        </span>
      </div>
      {phase.why && (
        <p className="text-[12px] text-text-secondary leading-snug mb-3">{phase.why}</p>
      )}
      <ul className="space-y-3">
        {(phase.exercises ?? []).map((ex, i) => (
          <li key={i} className="border-l-2 border-brand/30 pl-3">
            <p className="text-xs font-semibold text-text-primary leading-snug">{ex.exercise}</p>
            {ex.how && (
              <p className="text-[11px] text-text-secondary mt-1 leading-snug">
                <span className="font-medium text-brand">Como fazer:</span> {ex.how}
              </p>
            )}
            {ex.progression && (
              <p className="text-[11px] text-text-secondary mt-1 leading-snug">
                <span className="font-medium text-accent-green">Progressão:</span> {ex.progression}
              </p>
            )}
            {ex.source && (
              <p className="text-[10px] text-text-muted mt-0.5" title={ex.source}>📚 {ex.source}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
