import { Dumbbell, Timer, Zap, Trophy } from 'lucide-react'

const stations = [
  { name: 'SkiErg', icon: '🏋️', distance: '1000 m', pr: '4:12' },
  { name: 'Sled Push', icon: '🛷', distance: '50 m', pr: '0:38' },
  { name: 'Sled Pull', icon: '🛷', distance: '50 m', pr: '0:45' },
  { name: 'Burpee Broad Jump', icon: '🦘', distance: '80 m', pr: '2:18' },
  { name: 'Remo', icon: '🚣', distance: '1000 m', pr: '3:55' },
  { name: 'Farmers Carry', icon: '🏋️', distance: '200 m', pr: '1:22' },
  { name: 'Sandbag Lunges', icon: '🦵', distance: '100 m', pr: '2:05' },
  { name: 'Wall Balls', icon: '🎯', quantity: '100 reps', pr: '2:42' },
]

export default function HyroxScreen() {
  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight flex items-center gap-2">
            <Dumbbell size={24} className="text-lime" /> HYROX
          </h1>
          <p className="text-sm text-text-secondary mt-1">8 estações · 1 round = 8 km de corrida intercalada</p>
        </div>
        <div className="text-right px-4 py-2 rounded-xl bg-surface-200 border border-border-light">
          <p className="text-[10px] text-text-secondary uppercase tracking-wider">Personal Best</p>
          <p className="text-xl font-bold text-brand tabular-nums">1:14:22</p>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="kpi-card">
          <span className="text-xs text-text-secondary uppercase tracking-wider">Último treino</span>
          <span className="text-xl font-bold">1:18:45</span>
          <span className="text-xs text-accent-green">+4:23 do PB</span>
        </div>
        <div className="kpi-card">
          <span className="text-xs text-text-secondary uppercase tracking-wider">Treinos HYROX</span>
          <span className="text-xl font-bold">12</span>
          <span className="text-xs text-text-secondary">este ano</span>
        </div>
        <div className="kpi-card">
          <span className="text-xs text-text-secondary uppercase tracking-wider">Estação mais forte</span>
          <span className="text-xl font-bold text-accent-green">Remo</span>
          <span className="text-xs text-text-secondary">3:55 · Top 15%</span>
        </div>
        <div className="kpi-card">
          <span className="text-xs text-text-secondary uppercase tracking-wider">A melhorar</span>
          <span className="text-xl font-bold text-accent-orange">Wall Balls</span>
          <span className="text-xs text-text-secondary">2:42 · 2s acima da média</span>
        </div>
      </div>

      {/* Stations Grid */}
      <div>
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Timer size={18} className="text-lime" /> 8 Estações
        </h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {stations.map((station, i) => (
            <div key={station.name} className="card-hover p-5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-16 h-16 opacity-[0.03]">
                <span className="text-6xl">{station.icon}</span>
              </div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-2xl">{station.icon}</span>
                <span className="text-[10px] font-bold text-text-secondary bg-surface-300 px-2 py-0.5 rounded-full">
                  Station {i + 1}
                </span>
              </div>
              <h3 className="font-semibold text-text-primary">{station.name}</h3>
              <p className="text-sm text-text-secondary mt-0.5">
                {station.distance || station.quantity}
              </p>
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-border-light">
                <span className="text-xs text-text-secondary">PR</span>
                <span className="text-sm font-bold text-lime">{station.pr}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tips / Insights */}
      <div className="card-hover border-brand/10">
        <div className="flex items-start gap-4">
          <div className="shrink-0 grid place-items-center w-11 h-11 rounded-xl bg-brand/12 text-brand">
            <Zap size={20} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-brand flex items-center gap-2">
              Insight HYROX
            </h3>
            <p className="text-sm text-text-muted mt-2 leading-relaxed">
              Seu melhor split é no Remo (top 15%). O Wall Ball é onde perde mais tempo — 
              foco em potência de pernas e coordenação respiração-lançamento. Sugiro 2 sessões 
              específicas de Wall Ball por semana, 3 séries de 25 reps com 30s de descanso, 
              mirando execução contínua sem pausa.
            </p>
            <div className="flex flex-wrap gap-2 mt-3">
              <span className="text-[10px] bg-accent-green/10 text-accent-green px-2 py-1 rounded-md border border-accent-green/20">Remo: Top 15%</span>
              <span className="text-[10px] bg-accent-orange/10 text-accent-orange px-2 py-1 rounded-md border border-accent-orange/20">Wall Balls: -18% vs mediana</span>
              <span className="text-[10px] bg-surface-300 text-text-secondary px-2 py-1 rounded-md">Sled Push: +2% vs último treino</span>
            </div>
          </div>
        </div>
      </div>

      {/* Video placeholder */}
      <div className="card p-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-lime/10 flex items-center justify-center mx-auto mb-4">
          <Trophy size={28} className="text-lime" />
        </div>
        <h3 className="font-semibold text-lg">Modo HYROX Completo</h3>
        <p className="text-sm text-text-secondary mt-2 max-w-md mx-auto">
          Análise estação por estação, degradação muscular entre rounds, e recomendação de pace 
          para cada segmento de corrida. Disponível com o sensor IMU.
        </p>
        <span className="inline-block mt-4 text-xs bg-lime/10 text-lime px-3 py-1.5 rounded-full border border-lime/20 font-medium">
          Em breve
        </span>
      </div>
    </div>
  )
}
