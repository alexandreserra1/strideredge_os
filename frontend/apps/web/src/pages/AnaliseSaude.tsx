import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { ShieldCheck, Footprints, Activity, TrendingUp, Info, Sparkles } from 'lucide-react'
import { useActivities, useCoachVerdict, useTrainingLoad, latestAcwr } from '@strideredge/core'
import { mockTrainingLoad, mockAcwrCurrent, mockCoachVerdict, mockActivityDetail, mockActivities } from './mockData'

type Level = 'ok' | 'warn' | 'risk'
const levelMeta: Record<Level, { color: string; label: string; chip: string }> = {
  ok:   { color: '#34D399', label: 'Baixo',    chip: 'bg-accent-green/15 text-accent-green' },
  warn: { color: '#FBBF24', label: 'Moderado', chip: 'bg-accent-yellow/15 text-accent-yellow' },
  risk: { color: '#F87171', label: 'Alto',     chip: 'bg-accent-red/15 text-accent-red' },
}
const worst = (ls: Level[]): Level => ls.includes('risk') ? 'risk' : ls.includes('warn') ? 'warn' : 'ok'

export default function AnaliseSaude() {
  // ACWR + ramp reais quando o backend está up; fallback pro mock
  const { data: load } = useTrainingLoad()
  const { data: acts } = useActivities()
  const coach = useCoachVerdict()
  const isReal = !!acts?.length
  const review = isReal && coach.data ? coach.data : mockCoachVerdict
  const timeline = load?.length ? load : mockTrainingLoad
  const acwr = latestAcwr(load ?? []) ?? mockAcwrCurrent
  const ramp = (load?.[load.length - 1]?.ramp_pct) ?? mockAcwrCurrent.ramp_pct ?? 0
  const cadence = mockActivities[0].cadence
  const decoupling = mockActivityDetail.durability!.decoupling_pct

  const acwrLevel: Level = acwr.acwr < 0.8 ? 'warn' : acwr.acwr <= 1.3 ? 'ok' : acwr.acwr <= 1.5 ? 'warn' : 'risk'
  const cadLevel: Level = cadence >= 178 ? 'ok' : cadence >= 166 ? 'warn' : 'risk'
  const durLevel: Level = decoupling < 5 ? 'ok' : decoupling < 10 ? 'warn' : 'risk'
  const rampLevel: Level = ramp < 10 ? 'ok' : ramp <= 15 ? 'warn' : 'risk'

  const metrics = [
    { icon: ShieldCheck, label: 'Prontidão (ACWR)', value: acwr.acwr.toFixed(2), level: acwrLevel,
      why: 'Carga aguda (7d) ÷ crônica (28d). 0.8–1.3 = zona ideal; acima ~1.5 dispara risco.',
      source: 'PMC7047972' },
    { icon: Footprints, label: 'Cadência', value: `${cadence} spm`, level: cadLevel,
      why: 'Abaixo de 166 spm associa-se a risco tibial 6–7× maior. Alvo protetor: ≥178 spm.',
      source: 'PMC12440572' },
    { icon: Activity, label: 'Durabilidade', value: `${decoupling}%`, level: durLevel,
      why: 'Desacoplamento Pa:FC. <5% = segura bem o ritmo sob fadiga; >10% = "racha".',
      source: 'PMC12271085' },
    { icon: TrendingUp, label: 'Ramp semanal', value: `${ramp > 0 ? '+' : ''}${ramp}%`, level: rampLevel,
      why: 'Variação da carga semana a semana. Acima de 10% = aumento de carga arriscado.',
      source: 'Regra dos 10%' },
  ]
  const overall = worst(metrics.map(m => m.level))
  const ov = levelMeta[overall]

  const trend = timeline.slice(-21).map(t => ({
    day: new Date(t.day + 'T00:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
    acwr: Math.round((t.acwr ?? 0) * 100) / 100,
  }))

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Análise & Saúde</h1>
        <p className="text-text-secondary mt-1">Visão do atleta — risco de lesão e review da IA</p>
      </div>

      {/* Risco geral */}
      <div className="card flex items-center gap-4" style={{ borderColor: `${ov.color}44` }}>
        <div className="grid place-items-center w-14 h-14 rounded-2xl shrink-0" style={{ background: `${ov.color}1f`, color: ov.color }}>
          <ShieldCheck size={28} />
        </div>
        <div className="flex-1">
          <p className="text-xs text-text-secondary uppercase tracking-wider">Risco geral de lesão</p>
          <p className="text-2xl font-bold" style={{ color: ov.color }}>{ov.label}</p>
        </div>
        <p className="hidden sm:block text-sm text-text-secondary max-w-xs text-right">
          Combinação de carga, cadência, durabilidade e ramp semanal.
        </p>
      </div>

      {/* Painel de métricas de risco */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {metrics.map(({ icon: Icon, label, value, level, why, source }) => {
          const m = levelMeta[level]
          return (
            <div key={label} className="card-hover flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <div className="grid place-items-center w-9 h-9 rounded-xl" style={{ background: `${m.color}1f`, color: m.color }}>
                  <Icon size={18} />
                </div>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${m.chip}`}>{m.label}</span>
              </div>
              <div>
                <p className="text-xs text-text-secondary">{label}</p>
                <p className="text-2xl font-bold tabular-nums">{value}</p>
              </div>
              <p className="text-[11px] text-text-muted leading-snug flex-1">{why}</p>
              <span className="text-[10px] text-text-muted flex items-center gap-1"><Info size={10} /> {source}</span>
            </div>
          )
        })}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Review da IA */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Sparkles size={16} className="text-brand" /> Review da IA
              {isReal && coach.data && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-brand/12 text-brand">real</span>
              )}
            </h3>
            {isReal && (
              <button
                onClick={() => coach.mutate(acts![0].activity_id)}
                disabled={coach.isPending}
                className="btn-ghost text-xs"
              >
                {coach.isPending ? 'Analisando…' : coach.data ? 'Regerar' : 'Gerar do último treino'}
              </button>
            )}
          </div>

          {coach.isPending ? (
            <div className="flex items-center gap-3 p-4 rounded-xl bg-brand/[0.06] border border-brand/20 animate-fade-in">
              <Sparkles size={16} className="text-brand animate-pulse" />
              <div>
                <p className="text-sm font-medium">Analisando seu último treino…</p>
                <p className="text-xs text-text-secondary">O coach roda 100% local — leva alguns segundos.</p>
              </div>
            </div>
          ) : (
            <>
              {coach.isError && (
                <p className="text-xs text-accent-red mb-3">Não consegui gerar — o backend/Ollama está no ar?</p>
              )}
              {!(review.strengths?.length || review.improvements?.length || review.actions?.length) ? (
                <p className="text-sm text-text-muted leading-relaxed mb-4 whitespace-pre-line">{review.verdict}</p>
              ) : (
                <div className="space-y-3">
                  <ReviewList title="Pontos fortes" items={review.strengths} color="#34D399" glyph="✓" />
                  <ReviewList title="A melhorar" items={review.improvements} color="#FF8A4C" glyph="!" />
                  <ReviewList title="O que fazer" items={review.actions} color="#38BDF8" glyph="→" />
                </div>
              )}
              <div className="mt-4 pt-3 border-t border-border-light flex flex-wrap gap-2">
                {(review.citations ?? []).map((c, i) => (
                  <span key={i} className="text-[10px] text-text-secondary bg-surface-200 px-2 py-1 rounded-md">{c}</span>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Tendência de ACWR */}
        <div className="card">
          <h3 className="text-sm font-semibold mb-4">Prontidão ao longo do tempo</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
                <defs>
                  <linearGradient id="acwrGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6E56F7" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#6E56F7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} interval={3} />
                <YAxis domain={[0.4, 1.8]} tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} />
                <ReferenceLine y={0.8} stroke="#34D399" strokeDasharray="4 4" strokeOpacity={0.55} />
                <ReferenceLine y={1.3} stroke="#34D399" strokeDasharray="4 4" strokeOpacity={0.55} />
                <Tooltip content={<AcwrTooltip />} cursor={{ stroke: 'var(--border-medium)', strokeWidth: 1 }} />
                <Area type="monotone" dataKey="acwr" stroke="#6E56F7" strokeWidth={2.5} fill="url(#acwrGrad)"
                  dot={false} activeDot={{ r: 5, fill: '#6E56F7', stroke: 'var(--surface-100)', strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-text-muted mt-2">Entre as linhas tracejadas = zona segura (0.8–1.3).</p>
        </div>
      </div>
    </div>
  )
}

function AcwrTooltip({ active, payload }: { active?: boolean; payload?: Array<{ value: number }> }) {
  if (!active || !payload?.length) return null
  const v = payload[0].value
  const [label, color] =
    v < 0.8 ? ['Leve', '#38BDF8'] :
    v <= 1.3 ? ['Zona segura', '#34D399'] :
    v <= 1.5 ? ['Atenção', '#FBBF24'] : ['Risco', '#F87171']
  return (
    <div className="glass rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="font-bold tabular-nums">{v.toFixed(2)}</p>
      <p style={{ color }}>{label}</p>
    </div>
  )
}

function ReviewList({ title, items, color, glyph }: { title: string; items?: string[]; color: string; glyph: string }) {
  if (!items?.length) return null
  return (
    <div>
      <h4 className="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style={{ color }}>{title}</h4>
      <ul className="space-y-1.5">
        {items.map((s, i) => (
          <li key={i} className="text-xs text-text-muted flex items-start gap-2">
            <span className="mt-0.5 shrink-0" style={{ color }}>{glyph}</span>{s}
          </li>
        ))}
      </ul>
    </div>
  )
}
