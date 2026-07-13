import { useEffect, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Route, Footprints, Heart, Zap, Play, Clapperboard } from 'lucide-react'
import RouteMap from '../components/ui/RouteMap'
import InfoHint from '../components/ui/InfoHint'
import {
  useActivities, useActivity, useTrack, useTelemetry,
  toWorkoutSession, toZoneBars, toRoutePoints,
} from '@strideredge/core'
import {
  mockActivities, mockActivityDetail, mockTrack, mockTelemetry,
} from './mockData'

// Cor da barra pela intensidade (limite inferior ÷ FCmax) — frio -> quente
const zoneColor = (loFrac: number) =>
  loFrac < 0.5 ? '#6B7079' : loFrac < 0.6 ? '#38BDF8' : loFrac < 0.7 ? '#34D399'
  : loFrac < 0.8 ? '#FBBF24' : loFrac < 0.9 ? '#FF8A4C' : '#F87171'

// Zonas do MOCK no mesmo shape do adapter (fallback qdo o backend está off)
const mockZoneBars = [
  { label: 'Z1 · muito leve', pct: mockActivityDetail.hr_zones!.zone_1, loFrac: 0.5 },
  { label: 'Z2 · leve', pct: mockActivityDetail.hr_zones!.zone_2, loFrac: 0.6 },
  { label: 'Z3 · moderado', pct: mockActivityDetail.hr_zones!.zone_3, loFrac: 0.7 },
  { label: 'Z4 · forte', pct: mockActivityDetail.hr_zones!.zone_4, loFrac: 0.8 },
  { label: 'Z5 · máximo', pct: mockActivityDetail.hr_zones!.zone_5, loFrac: 0.9 },
]

export default function WorkoutDetail({ onNavigate, initialId }: {
  onNavigate: (r: string) => void
  initialId?: string | null      // deep-link: treino clicado no calendário/feed
}) {
  // Treinos REAIS quando o backend está up; fallback pro mock (a UI nunca quebra)
  const { data: apiActs } = useActivities()
  const isReal = !!apiActs?.length
  const activities = isReal ? apiActs!.map(toWorkoutSession) : mockActivities

  const [selectedId, setSelectedId] = useState<string | null>(initialId ?? null)

  // deep-link: o calendário/feed manda o treino a abrir
  useEffect(() => {
    if (initialId) setSelectedId(initialId)
  }, [initialId])

  const activity = activities.find(a => a.id === selectedId) || activities[0]

  // Detalhe/track/telemetria REAIS do treino selecionado (hooks só disparam com id real)
  const realId = isReal ? activity.id : undefined
  const { data: apiDetail } = useActivity(realId)
  const { data: apiTrack } = useTrack(realId)
  const { data: apiTele } = useTelemetry(realId)

  // Séries pros gráficos: telemetria real (downsample ~80 pontos) ou mock
  const teleSrc = apiTele?.length ? apiTele : mockTelemetry
  const step = Math.max(1, Math.floor(teleSrc.length / 80))
  const hrData = teleSrc.filter((_, i) => i % step === 0).map(t => ({
    time: new Date(t.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
    hr: t.heart_rate,
    cadence: t.cadence,
  }))
  const maxHr = apiTele?.length
    ? Math.max(...apiTele.map(t => t.heart_rate ?? 0))
    : mockActivityDetail.max_hr ?? 0

  // Zonas de FC: adapter do dado real, fallback mock
  // (durabilidade/decoupling foi pra Análise & Saúde — é julgamento de fadiga, não sinal do treino)
  const zoneBars = apiDetail ? toZoneBars(apiDetail) : mockZoneBars

  // Rota: track real ([] = indoor, sem GPS) ou mock
  const routeLL = apiTrack
    ? toRoutePoints(apiTrack)
    : mockTrack.points.map(p => ({ lat: p.smooth.lat, lon: p.smooth.lon, cadence: p.cadence }))

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

      {/* A análise de vídeo vive na sua própria página (Análise de Forma) — aqui só o atalho,
          pra não misturar a leitura do movimento com os dados do relógio. */}
      <button onClick={() => onNavigate('video')}
        className="card-hover w-full flex items-center justify-between text-left">
        <div className="flex items-center gap-3">
          <div className="grid place-items-center w-10 h-10 rounded-xl bg-brand/10 text-brand shrink-0">
            <Clapperboard size={18} />
          </div>
          <div>
            <p className="text-sm font-semibold">Analisar sua forma em vídeo</p>
            <p className="text-xs text-text-secondary mt-0.5">A IA desenha seu esqueleto e mede cadência, pisada, contato e mais.</p>
          </div>
        </div>
        <span className="text-brand text-sm font-medium shrink-0">Abrir →</span>
      </button>

      {/* Tira de métricas — compacta, secundária ao vídeo (números resumo do relógio) */}
      <div className="card grid grid-cols-3 md:grid-cols-5 gap-y-3 gap-x-2">
        {[
          { k: 'Distância', v: activity.distance_km || '—', u: activity.distance_km ? ' km' : '', c: '' },
          { k: 'Duração', v: activity.duration_min, u: ' min', c: '' },
          { k: 'Pace', v: activity.pace, u: '', c: '' },
          { k: 'FC média', v: activity.avg_hr || '—', u: activity.avg_hr ? ' bpm' : '', c: 'text-accent-red' },
          { k: 'Cadência', v: activity.cadence || '—', u: activity.cadence ? ' spm' : '', c: 'text-accent-green' },
        ].map(m => (
          <div key={m.k} className="text-center md:text-left">
            <p className="text-[10px] text-text-secondary uppercase tracking-wider">{m.k}</p>
            <p className={`text-lg font-bold tabular-nums ${m.c}`}>
              {m.v}{m.u && <span className="text-xs font-medium text-text-secondary">{m.u}</span>}
            </p>
          </div>
        ))}
      </div>

      {/* Detalhes do treino — contexto secundário, abaixo do carro-chefe */}
      <p className="text-xs font-semibold uppercase tracking-wider text-text-muted pt-2">Detalhes do treino</p>

      {/* Charts Row */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* HR Chart */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold flex items-center gap-1.5">
              <Heart size={14} className="text-accent-red" /> Frequência Cardíaca
              <InfoHint text="Batimentos por minuto ao longo do treino. É a medida direta do esforço do coração — sobe com a intensidade e com a fadiga." />
            </h3>
            <span className="text-xs text-text-secondary">Máx: {maxHr || '—'} bpm</span>
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
                  contentStyle={{ background: 'var(--surface-100)', border: '1px solid var(--border-light)', borderRadius: 12, fontSize: 11, color: 'var(--text-primary)' }}
                  labelStyle={{ color: 'var(--text-secondary)' }}
                  cursor={{ stroke: 'var(--border-medium)', strokeWidth: 1 }}
                />
                <Area type="monotone" dataKey="hr" stroke="#EF4444" strokeWidth={2} fill="url(#hrGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Cadência — mesma linha da FC (ambos são sinais no mesmo eixo de tempo) */}
        <div className="card">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-1.5">
            <Footprints size={14} className="text-accent-green" /> Cadência
            <InfoHint text="Passos por minuto (spm). Passada mais curta e rápida reduz o impacto por passo — abaixo de ~166 spm associa-se a mais risco de lesão na canela. Alvo protetor: ≥178 spm." />
          </h3>
          <div className="h-44">
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
                  contentStyle={{ background: 'var(--surface-100)', border: '1px solid var(--border-light)', borderRadius: 12, fontSize: 11, color: 'var(--text-primary)' }}
                  labelStyle={{ color: 'var(--text-secondary)' }}
                  cursor={{ stroke: 'var(--border-medium)', strokeWidth: 1 }}
                />
                <Area type="monotone" dataKey="cadence" stroke="#22C55E" strokeWidth={2} fill="url(#cadGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Tempo por Zona de FC — largura total */}
      <div className="card">
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-1.5">
          <Zap size={14} className="text-lime" /> Tempo por Zona de FC
          <InfoHint text="Quanto tempo você passou em cada faixa de esforço (das zonas de FC do relógio). Muito tempo nas zonas altas = treino intenso; a base aeróbia se constrói nas zonas baixas." />
        </h3>
        <div className="space-y-3">
          {zoneBars.map(z => (
            <div key={z.label} className="flex items-center gap-3">
              <span className="text-[10px] font-semibold w-24 text-text-secondary whitespace-nowrap">{z.label}</span>
              <div className="flex-1 h-3 bg-surface-300 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${z.pct}%`, backgroundColor: zoneColor(z.loFrac) }} />
              </div>
              <span className="text-xs text-text-secondary w-12 text-right tabular-nums">{z.pct}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Mapa · semáforo de cadência */}
      <div className="card overflow-hidden">
        <h3 className="text-sm font-semibold mb-4 flex items-center gap-2"><Route size={14} className="text-brand" /> Percurso · Semáforo de Cadência</h3>
        {routeLL.length > 1 ? (
          <div className="relative w-full h-64 md:h-80 rounded-xl overflow-hidden border border-border-light">
            <RouteMap points={routeLL} />
            {/* legenda */}
            <div className="absolute bottom-3 left-3 z-[1000] flex items-center gap-3 glass rounded-xl px-3 py-2 text-[10px]">
              <span className="flex items-center gap-1.5"><span className="w-3 h-1 rounded-full" style={{ background: '#34D399' }} /> ≥168 spm</span>
              <span className="flex items-center gap-1.5"><span className="w-3 h-1 rounded-full" style={{ background: '#FBBF24' }} /> 160–168</span>
              <span className="flex items-center gap-1.5"><span className="w-3 h-1 rounded-full" style={{ background: '#F87171' }} /> &lt;160</span>
            </div>
            <div className="absolute top-2 right-2 z-[1000] text-[9px] text-text-muted glass px-2 py-0.5 rounded">© OpenStreetMap · CARTO</div>
          </div>
        ) : (
          <div className="grid place-items-center h-40 rounded-xl border border-dashed border-border-medium text-center">
            <div>
              <p className="text-sm font-medium text-text-secondary">Treino indoor — sem GPS</p>
              <p className="text-xs text-text-muted mt-1">Esteira e treinos de força não geram trilha no mapa.</p>
            </div>
          </div>
        )}
      </div>

      {/* O veredito do Coach vive em Análise & Saúde — atalho pra não duplicar aqui */}
      <button onClick={() => onNavigate('analise')}
        className="card-hover w-full flex items-center justify-between text-left">
        <div>
          <p className="text-sm font-semibold">Quer a leitura do coach?</p>
          <p className="text-xs text-text-secondary mt-0.5">O veredito da IA e o risco de lesão ficam em Análise & Saúde.</p>
        </div>
        <span className="text-brand text-sm font-medium shrink-0">Abrir →</span>
      </button>
    </div>
  )
}


