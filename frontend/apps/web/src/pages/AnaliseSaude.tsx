import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { ShieldCheck, Footprints, Activity, TrendingUp, Sparkles } from 'lucide-react'
import { useActivities, useActivity, useCoachStream, useTrainingLoad, latestAcwr, toDurability } from '@strideredge/core'
import { mockTrainingLoad, mockAcwrCurrent, mockCoachVerdict, mockActivityDetail, mockActivities } from './mockData'
import InfoHint from '../components/ui/InfoHint'

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
  const coach = useCoachStream()
  const isReal = !!acts?.length
  const review = isReal && coach.data ? coach.data : mockCoachVerdict
  const timeline = load?.length ? load : mockTrainingLoad
  const acwr = latestAcwr(load ?? []) ?? mockAcwrCurrent
  const ramp = (load?.[load.length - 1]?.ramp_pct) ?? mockAcwrCurrent.ramp_pct ?? 0
  // cadência/durabilidade REAIS da última corrida (não do mock)
  const latestRun = acts?.find(a => String(a.primary_type).toUpperCase() === 'RUN')
  const { data: runDetail } = useActivity(latestRun?.activity_id)
  const cadence = latestRun?.avg_cadence ? Math.round(latestRun.avg_cadence) : mockActivities[0].cadence
  const realDur = runDetail ? toDurability(runDetail) : null
  const decoupling = realDur?.decoupling_pct ?? (isReal ? 0 : mockActivityDetail.durability!.decoupling_pct)

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
  // Índice de risco PONDERADO (0-100). Pesos pela força da evidência:
  // ACWR 40% (Gabbett/PMC7047972), ramp 25%, durabilidade 20%, cadência 15%.
  const W: Record<string, number> = { 'Prontidão (ACWR)': 0.4, 'Ramp semanal': 0.25, 'Durabilidade': 0.2, 'Cadência': 0.15 }
  const pts: Record<Level, number> = { ok: 0, warn: 50, risk: 100 }
  const riskScore = Math.round(metrics.reduce((acc, m) => acc + pts[m.level] * (W[m.label] ?? 0.15), 0))
  const overall: Level = riskScore < 25 ? 'ok' : riskScore < 55 ? 'warn' : 'risk'
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

      {/* Score geral — um único número em destaque (padrão "gait score"); o resto vira detalhe secundário */}
      <div className="card" style={{ borderColor: `${ov.color}44` }}>
        <div className="flex items-center gap-4">
          <div className="grid place-items-center w-16 h-16 rounded-2xl shrink-0" style={{ background: `${ov.color}1f`, color: ov.color }}>
            <ShieldCheck size={30} />
          </div>
          <div className="flex-1">
            <p className="text-xs text-text-secondary uppercase tracking-wider">Risco geral de lesão</p>
            <p className="text-3xl font-bold leading-tight" style={{ color: ov.color }}>
              {ov.label} <span className="text-base font-semibold text-text-secondary">· {riskScore}/100</span>
            </p>
          </div>
        </div>

        {/* as 4 métricas que compõem o score — pílulas compactas, explicação só no hover */}
        <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-border-light">
          {metrics.map(({ icon: Icon, label, value, level, why, source }) => {
            const m = levelMeta[level]
            return (
              <div key={label}
                className="flex items-center gap-2 rounded-full bg-surface-200 border border-border-light pl-2.5 pr-3 py-1.5">
                <Icon size={13} style={{ color: m.color }} />
                <span className="text-[11px] text-text-secondary whitespace-nowrap">{label}</span>
                <span className="text-xs font-bold tabular-nums" style={{ color: m.color }}>{value}</span>
                <InfoHint text={`${why} Fonte: ${source}.`} />
              </div>
            )
          })}
        </div>
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
                onClick={() => coach.start(acts![0].activity_id, !!coach.data)}
                disabled={coach.isStreaming}
                className="btn-ghost text-xs"
              >
                {coach.isStreaming ? 'Analisando…' : coach.data ? 'Regerar' : 'Gerar do último treino'}
              </button>
            )}
          </div>

          {coach.isStreaming ? (
            <div className="p-4 rounded-xl bg-brand/[0.06] border border-brand/20 animate-fade-in">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles size={14} className="text-brand animate-pulse" />
                <p className="text-xs font-medium text-text-secondary">
                  {coach.isCorrecting ? 'Detectei um dado não medido — corrigindo…' : 'Coach escrevendo · 100% local'}
                </p>
              </div>
              {coach.text && (
                <p className="text-sm leading-relaxed whitespace-pre-line">
                  {coach.text}<span className="text-brand animate-pulse">▍</span>
                </p>
              )}
            </div>
          ) : (
            <>
              {coach.isError && (
                <p className="text-xs text-accent-red mb-3">Não consegui gerar — o coach local está no ar?</p>
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
                    <stop offset="0%" stopColor="var(--brand-chart)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--brand-chart)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} interval={3} />
                <YAxis domain={[0.4, 1.8]} tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} />
                <ReferenceLine y={0.8} stroke="#34D399" strokeDasharray="4 4" strokeOpacity={0.55} />
                <ReferenceLine y={1.3} stroke="#34D399" strokeDasharray="4 4" strokeOpacity={0.55} />
                <Tooltip content={<AcwrTooltip />} cursor={{ stroke: 'var(--border-medium)', strokeWidth: 1 }} />
                <Area type="monotone" dataKey="acwr" stroke="var(--brand-chart)" strokeWidth={2.5} fill="url(#acwrGrad)"
                  dot={false} activeDot={{ r: 5, fill: 'var(--brand-chart)', stroke: 'var(--surface-100)', strokeWidth: 2 }} />
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
