import type {
  Activity, ActivityDetail, TrainingLoadItem, FitnessData,
  TrackData, CadenceSpectrum, WorkoutSession,
} from '@strideredge/core'

// ─── Activity Feed ───────────────────────────────────────
export const mockActivities: WorkoutSession[] = [
  { id: '1', type: 'run', name: 'Corrida Leve — Parque', distance_km: 8.4, duration_min: 44, pace: '5:14', avg_hr: 152, cadence: 168, calories: 487, elevation_gain: 56, date: '2026-06-28T07:30', route_name: 'Parque Ibirapuera' },
  { id: '2', type: 'treadmill', name: 'Intervalados — Esteira', distance_km: 6.0, duration_min: 32, pace: '5:20', avg_hr: 165, cadence: 172, calories: 412, elevation_gain: 0, date: '2026-06-26T18:00' },
  { id: '3', type: 'hyrox', name: 'HYROX Simulado', distance_km: 5.2, duration_min: 52, pace: '5:50', avg_hr: 171, cadence: 158, calories: 623, elevation_gain: 12, date: '2026-06-24T09:00' },
  { id: '4', type: 'strength', name: 'Força — Inferiores', distance_km: 0, duration_min: 45, pace: '—', avg_hr: 118, cadence: 0, calories: 298, elevation_gain: 0, date: '2026-06-23T18:30' },
  { id: '5', type: 'crossfit', name: 'WOD "Murph"', distance_km: 2.4, duration_min: 38, pace: '7:55', avg_hr: 164, cadence: 142, calories: 534, elevation_gain: 0, date: '2026-06-22T07:00' },
  { id: '6', type: 'run', name: 'Longão — Domingo', distance_km: 18.2, duration_min: 98, pace: '5:23', avg_hr: 149, cadence: 166, calories: 1045, elevation_gain: 134, date: '2026-06-20T06:45', route_name: 'Orla de Santos' },
  { id: '7', type: 'recovery', name: 'Recuperação Ativa', distance_km: 3.5, duration_min: 25, pace: '7:08', avg_hr: 128, cadence: 155, calories: 178, elevation_gain: 18, date: '2026-06-19T17:00' },
  { id: '8', type: 'run', name: 'Tiro — 5x1000m', distance_km: 7.0, duration_min: 34, pace: '4:51', avg_hr: 172, cadence: 176, calories: 498, elevation_gain: 22, date: '2026-06-18T06:30' },
]

// ─── ACWR / Training Load ─────────────────────────────────
export const mockTrainingLoad: TrainingLoadItem[] = Array.from({ length: 28 }, (_, i) => {
  const day = new Date(2026, 5, 1 + i)
  const load = [45, 32, 58, 40, 25, 62, 38, 50, 42, 55, 30, 48, 35, 60, 44, 52, 28, 56, 38, 50, 42, 58, 35, 55, 40, 48, 32, 50][i]
  const acute = i < 7 ? 45 : [44, 42, 46, 44, 42, 44, 43][i % 7]
  const chronic = i < 28 ? 42 : 44
  const acwr = acute / (chronic || 1)
  return {
    day: day.toISOString().split('T')[0],
    daily_load: load,
    acute_7d: acute,
    chronic_28d: chronic,
    acwr: Math.round(acwr * 100) / 100,
    days_of_history: i + 1,
    status: acwr < 0.8 ? 'low' : acwr <= 1.3 ? 'optimal' : acwr <= 1.5 ? 'high' : 'very_high',
    ramp_pct: Math.round((acute / (chronic || 1) - 1) * 100),
  }
})

// ─── Fitness / Race Predictions ──────────────────────────
export const mockFitness: FitnessData = {
  reference: { activity_id: '1', distance_m: 10000, duration_s: 2850 },
  predictions: {
    '5k': { distance_m: 5000, label: '5 km', predicted_seconds: 1320, predicted_pace: '4:24/km' },
    '10k': { distance_m: 10000, label: '10 km', predicted_seconds: 2790, predicted_pace: '4:39/km' },
    '21k': { distance_m: 21097, label: 'Meia Maratona', predicted_seconds: 6120, predicted_pace: '4:50/km' },
    '42k': { distance_m: 42195, label: 'Maratona', predicted_seconds: 12960, predicted_pace: '5:08/km' },
  },
  fitness: {
    trend: 'up',
    pct_change: 3.1,
    points: Array.from({ length: 30 }, (_, i) => ({
      day: new Date(2026, 5, 1 + i * 2).toISOString().split('T')[0],
      efficiency: 2.8 + Math.random() * 0.4 + i * 0.02,
    })),
  },
}

// ─── Activity Detail ───────────────────────────────────────
export const mockActivityDetail: ActivityDetail = {
  activity_id: '1',
  activity_name: 'Corrida Leve — Parque Ibirapuera',
  primary_type: 'run',
  start_time: '2026-06-28T07:30:00Z',
  distance_m: 8400,
  duration_s: 2640,
  avg_hr: 152,
  max_hr: 172,
  avg_cadence: 168,
  avg_pace: 5.23,
  total_elevation_gain: 56,
  calories: 487,
  avg_pace_min_km: '5:14',
  breaking_point: {
    timestamp: '2026-06-28T07:52:00Z',
    heart_rate: 168,
    cadence: 162,
  },
  efficiency: {
    overall: 3.15,
    flat: 3.42,
    uphill: 2.58,
  },
  durability: {
    decoupling_pct: 4.2,
    first_half_pa: 3.28,
    second_half_pa: 3.15,
  },
  hr_zones: {
    zone_1: 8,
    zone_2: 42,
    zone_3: 35,
    zone_4: 12,
    zone_5: 3,
  },
}

// ─── Track Data (simplified GPS trail) ─────────────────────
function generateTrack(numPoints: number): TrackData {
  const baseLat = -23.55
  const baseLon = -46.63
  const points = Array.from({ length: numPoints }, (_, i) => {
    const progress = i / numPoints
    const lat = baseLat + progress * 0.02 + Math.sin(i * 0.5) * 0.001
    const lon = baseLon + progress * 0.03 + Math.cos(i * 0.3) * 0.001
    const cadBase = 168 + Math.sin(i * 0.1) * 8
    const cad = i > numPoints * 0.7 ? cadBase - 10 - Math.random() * 8 : cadBase
    const jitter = (Math.random() - 0.5) * 0.0003
    return {
      raw: { lat: lat + jitter, lon: lon + jitter * 1.5 },
      smooth: { lat, lon },
      cadence: Math.round(cad),
    }
  })
  return { points }
}

export const mockTrack = generateTrack(120)

export const mockTelemetry = Array.from({ length: 240 }, (_, i) => ({
  timestamp: new Date(2026, 5, 28, 7, 30, i * 11).toISOString(),
  heart_rate: 140 + Math.round(Math.sin(i * 0.05) * 20 + i * 0.08),
  cadence: 165 + Math.round(Math.sin(i * 0.1) * 8),
  altitude: 740 + Math.round(Math.sin(i * 0.03) * 15),
  speed_ms: 3.1 + Math.sin(i * 0.05) * 0.4,
}))

export const mockSpectrum: CadenceSpectrum = {
  dominant_frequency_hz: 1.42,
  spectrum: {
    frequencies: Array.from({ length: 20 }, (_, i) => (i + 1) * 0.25),
    magnitudes: [2.1, 4.3, 8.2, 12.5, 9.8, 6.4, 3.2, 1.8, 0.9, 0.5, 0.3, 0.2, 0.1, 0.08, 0.05, 0.03, 0.02, 0.01, 0.01, 0.005],
  },
}

// ─── Coach Verdict ──────────────────────────────────────────
export const mockCoachVerdict = {
  verdict: 'Treino sólido, bem executado dentro das zonas propostas. O pacing foi consistente até o km 6, quando a cadência começou a cair — sinal clássico de fadiga muscular acumulada dos treinos de força de quarta. Para a próxima, sugiro iniciar os tiros já na cadência alvo (174+ spm) em vez de acelerar só no final. A eficiência metabólica em subida (2.58) é seu principal gargalo — inclui 2 sessões de subida semanal nos próximos 21 dias.',
  strengths: ['Pacing consistente nos primeiros 6km (±3s/km de variação)', 'FC controlada na Z2 durante 78% do treino', 'Hidratação e reposição corretas (sem queda de FC)'],
  improvements: ['Cadência caiu 10 spm no último terço — perda de economia de corrida', 'A eficiência em subida é 24% menor que o plano — prioridade de treino', 'Abertura de passada no final compensando a cadência baixa — risco de lesão no tibial'],
  actions: ['2x/semana treino de subida: 6x200m a 8% inclinação, cadência alta', 'Antes do intervalo, 10min de drills de cadência (liga/desliga 180bpm)', 'Próximo longão: foco em manter cadência ≥165 nos últimos 5km'],
  citations: ['PMC79011680 — Economia de corrida e cadência', 'PMC7047972 — Carga aguda/crônica e risco de lesão'],
}

// ─── Mock Activity list for the API response ──────────────
export const mockActivitiesList: Activity[] = mockActivities.map((w, i) => ({
  activity_id: String(i + 1),
  activity_name: w.name,
  primary_type: w.type,
  start_time: w.date,
  distance_m: w.distance_km * 1000,
  duration_s: w.duration_min * 60,
  avg_hr: w.avg_hr,
  avg_cadence: w.cadence || undefined,
}))

export const mockAcwrCurrent = mockTrainingLoad[mockTrainingLoad.length - 1]
