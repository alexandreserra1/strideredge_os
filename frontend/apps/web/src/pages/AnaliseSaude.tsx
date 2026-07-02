import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceArea } from 'recharts'
import { ShieldCheck, Footprints, Activity, TrendingUp, Info, Sparkles } from 'lucide-react'
import { useTrainingLoad, latestAcwr } from '@strideredge/core'
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
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
            <Sparkles size={16} className="text-brand" /> Review da IA
          </h3>
          <p className="text-sm text-text-muted leading-relaxed mb-4">{mockCoachVerdict.verdict}</p>
          <div className="space-y-3">
            <ReviewList title="Pontos fortes" items={mockCoachVerdict.strengths} color="#34D399" glyph="✓" />
            <ReviewList title="A melhorar" items={mockCoachVerdict.improvements} color="#FF8A4C" glyph="!" />
            <ReviewList title="O que fazer" items={mockCoachVerdict.actions} color="#38BDF8" glyph="→" />
          </div>
          <div className="mt-4 pt-3 border-t border-border-light flex flex-wrap gap-2">
            {mockCoachVerdict.citations.map((c, i) => (
              <span key={i} className="text-[10px] text-text-secondary bg-surface-200 px-2 py-1 rounded-md">{c}</span>
            ))}
          </div>
        </div>

        {/* Tendência de ACWR */}
        <div className="card">
          <h3 className="text-sm font-semibold mb-4">Prontidão ao longo do tempo</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
                <ReferenceArea y1={0.8} y2={1.3} fill="#34D399" fillOpacity={0.08} />
                <XAxis dataKey="day" tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} interval={3} />
                <YAxis domain={[0.4, 1.8]} tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: 'var(--surface-100)', border: '1px solid var(--border-light)', borderRadius: 12, fontSize: 11 }} />
                <Line type="monotone" dataKey="acwr" stroke="#6E56F7" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-text-muted mt-2">Faixa verde = zona segura (0.8–1.3).</p>
        </div>
      </div>
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
