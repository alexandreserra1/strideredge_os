import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { TrendingUp, Target, Flame, Wind, Footprints, ChevronRight, Play } from 'lucide-react'
import KpiCard from '../components/ui/KpiCard'
import AcwrGauge from '../components/ui/AcwrGauge'
import { useActivities, useTrainingLoad, toWorkoutSession, latestAcwr } from '@strideredge/core'
import { mockFitness, mockActivities, todayPrescribed, mockAcwrCurrent } from './mockData'

const weeklyVolume = [
  { name: 'Seg', volume: 0 }, { name: 'Ter', volume: 44 }, { name: 'Qua', volume: 0 },
  { name: 'Qui', volume: 0 }, { name: 'Sex', volume: 38 }, { name: 'Sáb', volume: 52 },
  { name: 'Dom', volume: 95 },
]

const progressPoints = mockFitness.fitness.points.map((p: { day: string; efficiency: number }) => ({
  day: new Date(p.day).toLocaleDateString('pt-BR', { day: 'numeric', month: 'short' }),
  efficiency: Math.round(p.efficiency * 100) / 100,
}))

const typeColors: Record<string, string> = {
  run: 'bg-accent-green/20 text-accent-green border-accent-green/30',
  treadmill: 'bg-accent-blue/20 text-accent-blue border-accent-blue/30',
  hyrox: 'bg-accent-orange/20 text-accent-orange border-accent-orange/30',
  crossfit: 'bg-accent-yellow/20 text-accent-yellow border-accent-yellow/30',
  strength: 'bg-accent-red/20 text-accent-red border-accent-red/30',
  recovery: 'bg-[#6B7079]/20 text-text-secondary border-[#6B7079]/30',
}

const typeLabels: Record<string, string> = {
  run: 'Corrida', treadmill: 'Esteira', hyrox: 'HYROX',
  crossfit: 'CrossFit', strength: 'Força', recovery: 'Recuperação',
}

export default function Dashboard({ onNavigate }: { onNavigate: (r: string) => void }) {
  // Dados REAIS quando o backend está no ar; fallback pro mock (a UI nunca quebra).
  const { data: apiActs } = useActivities()
  const { data: load } = useTrainingLoad()
  const activities = apiActs?.length ? apiActs.map(toWorkoutSession) : mockActivities
  const acwr = latestAcwr(load ?? []) ?? mockAcwrCurrent

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            Bom dia, <span className="text-brand">Rafa</span>
          </h1>
          <p className="text-text-secondary mt-1">Terça · 28 jun · Semana 26 do plano</p>
        </div>
        <button onClick={() => onNavigate('corrida')} className="btn-primary text-sm">
          <Play size={16} />
          Iniciar treino de hoje
        </button>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        <AcwrGauge value={acwr.acwr} status={acwr.status} />

        <KpiCard label="Fitness" value={`CTL ${mockFitness.fitness.pct_change > 0 ? '+' : ''}${mockFitness.fitness.pct_change.toFixed(1)}`}
          sub="Tendência de eficiência" icon={<TrendingUp size={16} />} accent="lime" trend={mockFitness.fitness.trend} />

        <KpiCard label="Previsão 10K" value={mockFitness.predictions['10k'].predicted_pace}
          sub={`${Math.round(mockFitness.predictions['10k'].predicted_seconds / 60)}min`}
          icon={<Target size={16} />} accent="blue" />

        <KpiCard label="Previsão 21K" value={mockFitness.predictions['21k'].predicted_pace}
          sub={`${Math.round(mockFitness.predictions['21k'].predicted_seconds / 60)}min`}
          icon={<Target size={16} />} accent="orange" />
      </div>

      {/* Today's Prescribed Workout */}
      <div className="card-hover">
        <div className="flex items-start justify-between mb-3">
          <div>
            <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">Hoje · Prescrito</span>
            <h3 className="text-lg font-semibold mt-0.5">{todayPrescribed.name}</h3>
          </div>
          {todayPrescribed.adjusted && (
            <span className="text-[10px] font-medium bg-lime/10 text-lime px-2 py-1 rounded-full border border-lime/20">
              🤖 Ajustado à prontidão
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <span className="text-text-muted">
            <span className="text-text-primary font-medium">{todayPrescribed.distance_km} km</span> · {todayPrescribed.duration_min} min
          </span>
          <span className="text-text-muted">
            Alvo: <span className="text-text-primary font-medium">{todayPrescribed.target_pace}</span>
          </span>
          <span className="text-text-muted">
            FC: <span className="text-text-primary font-medium">{todayPrescribed.target_hr}</span>
          </span>
        </div>
        <p className="text-sm text-text-secondary mt-2">{todayPrescribed.description}</p>
        <div className="flex gap-3 mt-4">
          <button className="btn-primary text-sm">
            <Play size={16} />
            Iniciar treino
          </button>
          <button className="btn-ghost text-sm">Adiar</button>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Fitness Trend */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold">Eficiência (velocidade ÷ FC)</h3>
            <span className="text-xs text-accent-green">
              {mockFitness.fitness.pct_change > 0 ? '+' : ''}{mockFitness.fitness.pct_change.toFixed(1)}% esta semana
            </span>
          </div>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={progressPoints}>
                <defs>
                  <linearGradient id="effGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6E56F7" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#6E56F7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#6B7079' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#6B7079' }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{ background: '#1C1F24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: '#9CA3AF' }}
                  itemStyle={{ color: '#6E56F7' }}
                />
                <Area type="monotone" dataKey="efficiency" stroke="#6E56F7" strokeWidth={2} fill="url(#effGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Weekly Volume */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold">Volume Semanal (min)</h3>
            <span className="text-xs text-text-secondary">Total: 229 min</span>
          </div>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weeklyVolume}>
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#6B7079' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#6B7079' }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{ background: '#1C1F24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: '#9CA3AF' }}
                  itemStyle={{ color: '#6E56F7' }}
                />
                <Bar dataKey="volume" fill="#6E56F7" radius={[4, 4, 0, 0]} barSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Activity Feed */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Atividades Recentes</h2>
          <button onClick={() => onNavigate('detalhe')}
            className="text-xs text-text-secondary hover:text-text-primary flex items-center gap-1 transition-colors">
            Ver todos <ChevronRight size={14} />
          </button>
        </div>
        <div className="space-y-2">
          {activities.slice(0, 5).map((act) => (
            <button
              key={act.id}
              onClick={() => onNavigate('detalhe')}
              className="w-full card-hover flex items-center gap-4 p-4 text-left"
            >
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xs font-bold border ${typeColors[act.type]}`}>
                {act.type === 'run' ? <Footprints size={18} /> :
                 act.type === 'hyrox' ? <Flame size={18} /> :
                 act.type === 'strength' ? <Wind size={18} /> : <TrendingUp size={18} />}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">{act.name}</p>
                <p className="text-xs text-text-secondary">{typeLabels[act.type]} · {new Date(act.date).toLocaleDateString('pt-BR', { day: 'numeric', month: 'short' })}</p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-sm font-semibold text-text-primary">{act.distance_km > 0 ? `${act.distance_km} km` : `${act.duration_min} min`}</p>
                <p className="text-xs text-text-secondary">
                  {act.pace} · {act.avg_hr} bpm
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
