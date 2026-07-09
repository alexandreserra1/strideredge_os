import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { TrendingUp, Target, Play } from 'lucide-react'
import KpiCard from '../components/ui/KpiCard'
import AcwrGauge from '../components/ui/AcwrGauge'
import InfoHint from '../components/ui/InfoHint'
import WorkoutCalendar from '../components/ui/WorkoutCalendar'
import { useActivities, useTrainingLoad, useFitness, toWorkoutSession, latestAcwr, toFitnessUi, weeklyVolume, toCalendarDays } from '@strideredge/core'
import { mockFitness, mockActivities, mockAcwrCurrent } from './mockData'

export default function Dashboard({ onNavigate, onOpenWorkout }: {
  onNavigate: (r: string) => void
  onOpenWorkout?: (id: string) => void
}) {
  // Dados REAIS quando o backend está no ar; fallback pro mock (a UI nunca quebra).
  const { data: apiActs } = useActivities()
  const { data: load } = useTrainingLoad()
  const { data: apiFit } = useFitness()
  const activities = apiActs?.length ? apiActs.map(toWorkoutSession) : mockActivities
  const acwr = latestAcwr(load ?? []) ?? mockAcwrCurrent

  // Fitness real (previsões Riegel + tendência de eficiência) ou mock
  const fit = (apiFit && toFitnessUi(apiFit)) || {
    trend: mockFitness.fitness.trend, trendLabel: '',
    pctChange: mockFitness.fitness.pct_change,
    points: mockFitness.fitness.points,
    predictions: {
      '10k': { pace: mockFitness.predictions['10k'].predicted_pace, minutes: Math.round(mockFitness.predictions['10k'].predicted_seconds / 60) },
      '21k': { pace: mockFitness.predictions['21k'].predicted_pace, minutes: Math.round(mockFitness.predictions['21k'].predicted_seconds / 60) },
    },
  }
  const progressPoints = fit.points.map(pt => ({
    day: new Date(pt.day).toLocaleDateString('pt-BR', { day: 'numeric', month: 'short' }),
    efficiency: Math.round(pt.efficiency * 100) / 100,
  }))

  // Volume da semana corrente (min/dia) calculado das sessões
  const volume = weeklyVolume(activities)
  const volumeTotal = volume.reduce((acc, v) => acc + v.volume, 0)

  // Calendário de treinos (a home é o log; clicar num dia abre o treino)
  const calendarDays = apiActs?.length
    ? toCalendarDays(apiActs)
    : Object.fromEntries(mockActivities.map(a => [a.date.slice(0, 10), { activityId: a.id, type: a.type }]))

  // Saudação honesta (hora local) + data real
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite'
  const raw = new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })
  const todayLabel = raw.charAt(0).toUpperCase() + raw.slice(1)

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            {greeting}, <span className="text-brand">atleta</span>
          </h1>
          <p className="text-text-secondary mt-1">{todayLabel}</p>
        </div>
        <button onClick={() => onNavigate('corrida')} className="btn-primary text-sm">
          <Play size={16} />
          Iniciar treino de hoje
        </button>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        <AcwrGauge value={acwr.acwr} status={acwr.status} />

        <KpiCard label="Fitness" value={`${fit.pctChange > 0 ? '+' : ''}${fit.pctChange.toFixed(1)}%`}
          sub={`Eficiência (vel ÷ FC)${fit.trendLabel ? ` · ${fit.trendLabel}` : ' · 14 dias'}`}
          hint="Quão em forma você está: eficiência = velocidade por batimento. Sobe quando você corre mais rápido com a mesma FC."
          icon={<TrendingUp size={16} />} accent="green" trend={fit.trend} />

        <KpiCard label="Previsão 10K" value={fit.predictions['10k']?.pace ?? '—'}
          sub={fit.predictions['10k'] ? `${fit.predictions['10k'].minutes}min` : 'sem referência'}
          hint="Tempo estimado de prova (modelo de Riegel), projetado a partir da sua melhor corrida recente."
          icon={<Target size={16} />} accent="blue" />

        <KpiCard label="Previsão 21K" value={fit.predictions['21k']?.pace ?? '—'}
          sub={fit.predictions['21k'] ? `${fit.predictions['21k'].minutes}min` : 'sem referência'}
          hint="Tempo estimado de prova (modelo de Riegel). Mais preciso perto da distância que você treina."
          icon={<Target size={16} />} accent="orange" />
      </div>

      {/* Charts Row */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Fitness Trend */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold flex items-center gap-1.5">
              Eficiência (velocidade ÷ FC)
              <InfoHint text="Velocidade dividida pela frequência cardíaca. Sobe quando você corre mais rápido com o mesmo esforço — o melhor sinal de que a base aeróbia está melhorando." />
            </h3>
            <span className="text-xs text-accent-green">
              {fit.pctChange > 0 ? '+' : ''}{fit.pctChange.toFixed(1)}% na janela
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
                  contentStyle={{ background: 'var(--surface-100)', border: '1px solid var(--border-light)', borderRadius: 12, fontSize: 12, color: 'var(--text-primary)' }}
                  labelStyle={{ color: 'var(--text-secondary)' }}
                  itemStyle={{ color: '#6E56F7' }}
                  cursor={{ stroke: 'var(--border-medium)', strokeWidth: 1 }}
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
            <span className="text-xs text-text-secondary">Total: {volumeTotal} min</span>
          </div>
          <div className="h-36 relative">
            {volumeTotal === 0 && (
              <p className="absolute inset-0 grid place-items-center text-xs text-text-muted z-10">
                Sem treinos nesta semana — bora começar? 🏃
              </p>
            )}
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={volume}>
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#6B7079' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#6B7079' }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{ background: 'var(--surface-100)', border: '1px solid var(--border-light)', borderRadius: 12, fontSize: 12, color: 'var(--text-primary)' }}
                  labelStyle={{ color: 'var(--text-secondary)' }}
                  itemStyle={{ color: '#6E56F7' }}
                  cursor={{ fill: 'var(--surface-300)', opacity: 0.5 }}
                />
                <Bar dataKey="volume" fill="#6E56F7" radius={[4, 4, 0, 0]} barSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Calendário de treinos — o log da home; clicar num dia abre o treino */}
      <WorkoutCalendar days={calendarDays} onOpenWorkout={onOpenWorkout} />
    </div>
  )
}
