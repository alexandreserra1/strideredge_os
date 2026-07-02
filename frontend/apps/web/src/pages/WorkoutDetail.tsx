import { useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { Route, Footprints, Heart, Zap, TrendingUp, Play } from 'lucide-react'
import {
  mockActivities, mockActivityDetail, mockTrack, mockSpectrum,
  mockTelemetry, mockCoachVerdict,
} from './mockData'

const hrZones = [
  { zone: 'Z1', pct: mockActivityDetail.hr_zones!.zone_1, label: 'Muito leve', color: '#6B7079' },
  { zone: 'Z2', pct: mockActivityDetail.hr_zones!.zone_2, label: 'Leve', color: '#22C55E' },
  { zone: 'Z3', pct: mockActivityDetail.hr_zones!.zone_3, label: 'Moderado', color: '#6E56F7' },
  { zone: 'Z4', pct: mockActivityDetail.hr_zones!.zone_4, label: 'Forte', color: '#F97316' },
  { zone: 'Z5', pct: mockActivityDetail.hr_zones!.zone_5, label: 'Máximo', color: '#EF4444' },
]

export default function WorkoutDetail({ onNavigate }: { onNavigate: (r: string) => void }) {
  const [selectedId, setSelectedId] = useState(mockActivities[0].id)
  const [showCoach, setShowCoach] = useState(false)

  const activity = mockActivities.find(a => a.id === selectedId) || mockActivities[0]
  const detail = mockActivityDetail
  const track = mockTrack
  const verdict = mockCoachVerdict

  // Extract HR and cadence data for charts
  const hrData = mockTelemetry.filter((_, i) => i % 6 === 0).map(t => ({
    time: new Date(t.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
    hr: t.heart_rate,
    cadence: t.cadence,
  }))

  // Rota normalizada pra caber no mapa (viewBox 160x90 com padding), independente do GPS
  const MW = 160, MH = 90, PAD = 16
  const lons = track.points.map(p => p.smooth.lon)
  const lats = track.points.map(p => p.smooth.lat)
  const minLon = Math.min(...lons), spanLon = (Math.max(...lons) - minLon) || 1e-6
  const minLat = Math.min(...lats), spanLat = (Math.max(...lats) - minLat) || 1e-6
  const routePoints = track.points.map(p => ({
    x: PAD + ((p.smooth.lon - minLon) / spanLon) * (MW - 2 * PAD),
    y: PAD + (1 - (p.smooth.lat - minLat) / spanLat) * (MH - 2 * PAD),
    cadence: p.cadence,
  }))
  const cadColor = (cad: number) => cad >= 168 ? '#34D399' : cad >= 160 ? '#F5B14C' : '#FB5E7E'
  const marker = routePoints[Math.floor(routePoints.length * 0.6)] || routePoints[0]

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">{activity.name}</h1>
          <p className="text-sm text-text-secondary mt-1">
            {new Date(activity.date).toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
            · {activity.route_name || ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-ghost text-xs">Compartilhar</button>
          <button onClick={() => onNavigate('corrida')} className="btn-primary text-sm">
            <Play size={14} /> Replay
          </button>
        </div>
      </div>

      {/* Activity Strip */}
      <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
        {mockActivities.map(act => (
          <button
            key={act.id}
            onClick={() => setSelectedId(act.id)}
            className={`shrink-0 px-4 py-2.5 rounded-xl text-xs font-medium border transition-all duration-200 whitespace-nowrap
              ${selectedId === act.id
                ? 'bg-lime/10 text-lime border-lime/20'
                : 'bg-surface-200 text-text-secondary border-border-light hover:border-border-medium hover:text-text-primary'
              }`}
          >
            <span className="block font-semibold">{act.name.split(' — ')[0]}</span>
            <span className="block mt-0.5 opacity-60">{act.distance_km} km · {act.pace}</span>
          </button>
        ))}
      </div>

      {/* Hero Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="kpi-card">
          <span className="text-xs text-text-secondary uppercase tracking-wider">Distância</span>
          <span className="text-xl md:text-2xl font-bold">{activity.distance_km} <span className="text-sm font-medium text-text-secondary">km</span></span>
        </div>
        <div className="kpi-card">
          <span className="text-xs text-text-secondary uppercase tracking-wider">Duração</span>
          <span className="text-xl md:text-2xl font-bold">{activity.duration_min} <span className="text-sm font-medium text-text-secondary">min</span></span>
        </div>
        <div className="kpi-card">
          <span className="text-xs text-text-secondary uppercase tracking-wider">Pace médio</span>
          <span className="text-xl md:text-2xl font-bold">{activity.pace}</span>
        </div>
        <div className="kpi-card">
          <span className="text-xs text-text-secondary uppercase tracking-wider">FC média</span>
          <span className="text-xl md:text-2xl font-bold text-accent-red">{activity.avg_hr} <span className="text-sm font-medium text-text-secondary">bpm</span></span>
        </div>
        <div className="kpi-card">
          <span className="text-xs text-text-secondary uppercase tracking-wider">Cadência</span>
          <span className="text-xl md:text-2xl font-bold text-accent-green">{activity.cadence} <span className="text-sm font-medium text-text-secondary">spm</span></span>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* HR Chart */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold flex items-center gap-2"><Heart size={14} className="text-accent-red" /> Frequência Cardíaca</h3>
            <span className="text-xs text-text-secondary">Máx: {detail.max_hr} bpm</span>
          </div>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={hrData}>
                <defs>
                  <linearGradient id="hrGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#EF4444" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#EF4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} interval={3} />
                <YAxis domain={[80, 190]} tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{ background: '#1C1F24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, fontSize: 11 }}
                  labelStyle={{ color: '#9CA3AF' }}
                />
                <Area type="monotone" dataKey="hr" stroke="#EF4444" strokeWidth={2} fill="url(#hrGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* HR Zones */}
        <div className="card">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2"><Zap size={14} className="text-lime" /> Tempo por Zona de FC</h3>
          <div className="space-y-3">
            {hrZones.map(z => (
              <div key={z.zone} className="flex items-center gap-3">
                <span className="text-xs font-semibold w-6 text-text-secondary">{z.zone}</span>
                <div className="flex-1 h-3 bg-surface-300 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-500" style={{ width: `${z.pct}%`, backgroundColor: z.color }} />
                </div>
                <div className="flex items-center gap-2 w-24 justify-end">
                  <span className="text-xs text-text-secondary">{z.pct}%</span>
                  <span className="text-[10px] text-text-secondary">{z.label}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Cadence + Spectrum */}
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2"><Footprints size={14} className="text-accent-green" /> Cadência</h3>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={hrData}>
                <defs>
                  <linearGradient id="cadGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22C55E" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#22C55E" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} interval={3} />
                <YAxis domain={[140, 185]} tick={{ fontSize: 9, fill: '#6B7079' }} axisLine={false} tickLine={false} width={30} />
                <Tooltip
                  contentStyle={{ background: '#1C1F24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, fontSize: 11 }}
                  labelStyle={{ color: '#9CA3AF' }}
                />
                <Area type="monotone" dataKey="cadence" stroke="#22C55E" strokeWidth={2} fill="url(#cadGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Durability / Decoupling */}
        <div className="card">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2"><TrendingUp size={14} className="text-accent-blue" /> Durabilidade</h3>
          <div className="flex items-center gap-6">
            <div>
              <p className="text-3xl font-bold text-accent-blue">{detail.durability!.decoupling_pct}%</p>
              <p className="text-xs text-text-secondary mt-1">Decoupling Pa:FC</p>
            </div>
            <div className="flex-1 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">1ª metade</span>
                <span className="font-medium">{detail.durability!.first_half_pa.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">2ª metade</span>
                <span className="font-medium">{detail.durability!.second_half_pa.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">Status</span>
                <span className={`font-medium ${detail.durability!.decoupling_pct < 5 ? 'text-accent-green' : detail.durability!.decoupling_pct < 10 ? 'text-accent-yellow' : 'text-accent-red'}`}>
                  {detail.durability!.decoupling_pct < 5 ? 'Bom' : detail.durability!.decoupling_pct < 10 ? 'Atenção' : 'Alto'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Mapa · semáforo de cadência */}
      <div className="card overflow-hidden">
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2"><Route size={14} className="text-brand" /> Percurso · Semáforo de Cadência</h3>
        <div className="relative w-full h-64 md:h-80 rounded-xl overflow-hidden border border-border-light"
          style={{ background: 'radial-gradient(120% 130% at 50% 0%, var(--surface-300), var(--surface-bg))' }}>
          <svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid meet" className="absolute inset-0 w-full h-full">
            {/* trilha em segmentos coloridos pela cadência */}
            {routePoints.slice(0, -1).map((p, i) => {
              const n = routePoints[i + 1]
              return <line key={i} x1={p.x} y1={p.y} x2={n.x} y2={n.y}
                stroke={cadColor(p.cadence)} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
            })}
            {/* largada */}
            <circle cx={routePoints[0].x} cy={routePoints[0].y} r={3} fill="var(--surface-bg)" stroke="#34D399" strokeWidth={2} />
            {/* posição do atleta (marcador pulsante) */}
            <g>
              <circle cx={marker.x} cy={marker.y} r={4.5} fill="none" stroke="#6E56F7" strokeWidth={1.5}
                style={{ transformBox: 'fill-box', transformOrigin: 'center' }} className="animate-pulse-ring" />
              <circle cx={marker.x} cy={marker.y} r={3.6} fill="#6E56F7" />
              <circle cx={marker.x} cy={marker.y} r={1.4} fill="#fff" />
            </g>
            {/* chegada */}
            <circle cx={routePoints[routePoints.length - 1].x} cy={routePoints[routePoints.length - 1].y} r={3} fill="var(--surface-bg)" stroke="#FB5E7E" strokeWidth={2} />
          </svg>

          {/* legenda */}
          <div className="absolute bottom-3 left-3 flex items-center gap-3 glass rounded-xl px-3 py-2 text-[10px]">
            <span className="flex items-center gap-1.5"><span className="w-3 h-1.5 rounded-full" style={{ background: '#34D399' }} /> ≥168 spm</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-1.5 rounded-full" style={{ background: '#F5B14C' }} /> 160–168</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-1.5 rounded-full" style={{ background: '#FB5E7E' }} /> &lt;160</span>
          </div>
          <div className="absolute top-3 right-3 text-[10px] text-text-muted glass px-2 py-1 rounded-lg">Mapa com tiles chega no app</div>
        </div>
      </div>

      {/* Coach Verdict */}
      <div className="card-hover border-lime/10" id="coach-verdict">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            <div>
              <h3 className="text-lg font-bold flex items-center gap-2">
                Veredito do Coach
                <span className="text-[10px] bg-lime/10 text-lime px-2 py-0.5 rounded-full border border-lime/20 font-medium">B+</span>
              </h3>
              <p className="text-xs text-text-secondary">Análise gerada por IA · Qwen 2.7B + RAG</p>
            </div>
          </div>
          <button onClick={() => setShowCoach(!showCoach)} className="btn-ghost text-xs shrink-0">
            {showCoach ? 'Ocultar' : 'Ler análise'}
          </button>
        </div>

        <p className="text-sm leading-relaxed text-text-muted mb-6">{verdict.verdict}</p>

        {showCoach && (
          <div className="grid md:grid-cols-3 gap-4 animate-fade-in">
            <div className="bg-accent-green/5 rounded-xl p-4 border border-accent-green/10">
              <h4 className="text-xs font-semibold text-accent-green uppercase tracking-wider mb-3">Pontos fortes</h4>
              <ul className="space-y-2">
                {verdict.strengths.map((s, i) => (
                  <li key={i} className="text-xs text-text-muted flex items-start gap-2">
                    <span className="text-accent-green mt-0.5 shrink-0">✓</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-accent-orange/5 rounded-xl p-4 border border-accent-orange/10">
              <h4 className="text-xs font-semibold text-accent-orange uppercase tracking-wider mb-3">A melhorar</h4>
              <ul className="space-y-2">
                {verdict.improvements.map((s, i) => (
                  <li key={i} className="text-xs text-text-muted flex items-start gap-2">
                    <span className="text-accent-orange mt-0.5 shrink-0">!</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-accent-blue/5 rounded-xl p-4 border border-accent-blue/10">
              <h4 className="text-xs font-semibold text-accent-blue uppercase tracking-wider mb-3">O que fazer</h4>
              <ul className="space-y-2">
                {verdict.actions.map((s, i) => (
                  <li key={i} className="text-xs text-text-muted flex items-start gap-2">
                    <span className="text-accent-blue mt-0.5 shrink-0">→</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Citations */}
        {showCoach && (
          <div className="mt-4 pt-4 border-t border-border-light">
            <p className="text-[10px] text-text-secondary font-medium uppercase tracking-wider mb-2">Fontes</p>
            <div className="flex flex-wrap gap-2">
              {verdict.citations.map((c, i) => (
                <span key={i} className="text-[10px] bg-white/5 text-text-secondary px-2 py-1 rounded-md">{c}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}


