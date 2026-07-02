import { useState } from 'react'
import { ChevronLeft, ChevronRight, CalendarDays, Target, Clock, Zap, X, Play } from 'lucide-react'
import { mockPlan } from './mockData'
import type { PrescribedWorkout } from '@strideredge/core'

const typeIcon: Record<string, string> = {
  run: '🏃',
  treadmill: '🏃',
  hyrox: '🏋️',
  crossfit: '💪',
  strength: '🏋️',
  recovery: '🧘',
}

const typeColor: Record<string, string> = {
  run: 'border-accent-green/30 bg-accent-green/10',
  treadmill: 'border-accent-blue/30 bg-accent-blue/10',
  hyrox: 'border-accent-orange/30 bg-accent-orange/10',
  crossfit: 'border-accent-yellow/30 bg-accent-yellow/10',
  strength: 'border-accent-red/30 bg-accent-red/10',
  recovery: 'border-[#6B7079]/30 bg-[#6B7079]/10',
}

export default function PlanScreen() {
  const [currentWeek, setCurrentWeek] = useState(0)
  const [viewMode, setViewMode] = useState<'week' | 'month'>('week')
  const [selectedDay, setSelectedDay] = useState<PrescribedWorkout | null>(null)
  const plan = mockPlan[currentWeek]

  const race = {
    name: 'Meia Maratona SP',
    date: '20 SET 2026',
    weeksLeft: 8,
    totalWeeks: 12,
    progress: 33,
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Plano de Treino</h1>
          <p className="text-sm text-text-secondary mt-1">Preparação para {race.name}</p>
        </div>
      </div>

      {/* Race Header */}
      <div className="card-hover bg-gradient-to-br from-surface-200 to-surface overflow-hidden">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs text-text-secondary mb-1">
              <Target size={12} /> Prova-alvo
            </div>
            <h2 className="text-xl md:text-2xl font-bold">{race.name}</h2>
            <p className="text-sm text-text-muted mt-1">{race.date} · {race.weeksLeft} semanas restantes</p>
          </div>
          <span className="text-3xl">🏅</span>
        </div>
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-text-secondary mb-1.5">
            <span>{race.progress}% concluído</span>
            <span>{race.totalWeeks} semanas</span>
          </div>
          <div className="h-2 bg-surface-300 rounded-full overflow-hidden">
            <div className="h-full bg-lime rounded-full transition-all duration-500" style={{ width: `${race.progress}%` }} />
          </div>
        </div>
      </div>

      {/* Week Navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCurrentWeek(Math.max(0, currentWeek - 1))}
            disabled={currentWeek === 0}
            className="p-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-white/5 dark:hover:bg-white/5 disabled:opacity-30 transition-all"
          >
            <ChevronLeft size={18} />
          </button>
          <h2 className="text-lg font-semibold min-w-[120px] text-center">{plan.label}</h2>
          <button
            onClick={() => setCurrentWeek(Math.min(mockPlan.length - 1, currentWeek + 1))}
            disabled={currentWeek === mockPlan.length - 1}
            className="p-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-white/5 dark:hover:bg-white/5 disabled:opacity-30 transition-all"
          >
            <ChevronRight size={18} />
          </button>
        </div>
        <div className="flex items-center bg-surface-300 rounded-xl p-0.5">
          <button
            onClick={() => setViewMode('week')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${viewMode === 'week' ? 'bg-surface-100 text-text-primary' : 'text-text-secondary hover:text-text-primary'}`}
          >
            Semana
          </button>
          <button
            onClick={() => setViewMode('month')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${viewMode === 'month' ? 'bg-surface-100 text-text-primary' : 'text-text-secondary hover:text-text-primary'}`}
          >
            Mês
          </button>
        </div>
      </div>

      {/* Week Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {plan.days.map((day: PrescribedWorkout) => {
          const d = new Date(day.day + 'T00:00:00')
          const dayNum = d.getDate()
          const dayName = d.toLocaleDateString('pt-BR', { weekday: 'short' })
          const isToday = day.day === new Date().toISOString().split('T')[0]
          return (
            <button
              key={day.day}
              onClick={() => setSelectedDay(day)}
              className={`card-hover text-left p-4 relative ${typeColor[day.type]}
                ${isToday ? 'ring-1 ring-lime' : ''}`}
            >
              {isToday && (
                <span className="absolute -top-1.5 -right-1.5 text-[9px] bg-lime text-surface-50 font-bold px-1.5 py-0.5 rounded-full">Hoje</span>
              )}
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-text-secondary">{dayName}</span>
                <span className="text-base">{typeIcon[day.type]}</span>
              </div>
              <p className="text-lg font-bold text-text-primary">{dayNum}</p>
              <p className="text-xs font-medium mt-1 leading-tight">{day.name}</p>
              {day.duration_min && (
                <p className="text-[10px] text-text-secondary mt-1">{day.duration_min} min</p>
              )}
            </button>
          )
        })}
      </div>

      {/* Prescribed Sheet (Drawer) */}
      {selectedDay && (
        <div className="fixed inset-0 z-50 flex justify-end" onClick={() => setSelectedDay(null)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-md bg-surface-100 border-l border-border-light h-full overflow-y-auto animate-slide-in"
            onClick={e => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-surface-100/95 backdrop-blur-xl border-b border-border-light p-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-text-secondary">
                  {new Date(selectedDay.day + 'T00:00:00').toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })}
                </p>
                <h2 className="text-lg font-bold">{selectedDay.name}</h2>
              </div>
              <button onClick={() => setSelectedDay(null)} className="p-2 rounded-xl hover:bg-white/5 dark:hover:bg-white/5 transition-colors">
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-6">
              {/* Adjusted badge */}
              <span className="inline-flex items-center gap-1 text-xs bg-lime/10 text-lime px-3 py-1.5 rounded-full border border-lime/20">
                <Zap size={12} /> Ajustado à sua prontidão
              </span>

              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Aquecimento</h3>
                <div className="card p-4">
                  <p className="text-sm font-medium">10 min corrida leve progressiva</p>
                  <p className="text-xs text-text-secondary mt-1">Pace: {selectedDay.target_pace || '5:30/km'} → FC: {selectedDay.target_hr || '145-155 bpm'}</p>
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Bloco Principal</h3>
                <div className="card p-4 border-lime/20">
                  <p className="text-sm font-medium">{selectedDay.description}</p>
                  <div className="flex gap-4 mt-2 text-xs text-text-secondary">
                    <span>⏱ {selectedDay.duration_min} min</span>
                    {selectedDay.distance_km && <span>📏 {selectedDay.distance_km} km</span>}
                    {selectedDay.target_pace && <span>🎯 {selectedDay.target_pace}</span>}
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Desaquecimento</h3>
                <div className="card p-4">
                  <p className="text-sm font-medium">5 min caminhada + alongamento</p>
                  <p className="text-xs text-text-secondary mt-1">FC abaixo de 120 bpm</p>
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button className="btn-primary flex-1">
                  <Play size={16} /> Iniciar treino
                </button>
                <button className="btn-ghost flex-1">Adiar</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
