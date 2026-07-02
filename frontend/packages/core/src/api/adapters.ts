// Adaptadores backend -> shapes que a UI usa (o backend fala outra "língua":
// primary_type MAIÚSCULO, status ACWR em português, distância em metros...).
import type {
  Activity, ActivityType, WorkoutSession, TrainingLoadItem, AcwrStatus,
  ApiActivityDetail, ApiTrack,
} from '../types'

const TYPE_MAP: Record<string, ActivityType> = {
  RUN: 'run', CARDIO: 'treadmill', HIIT: 'crossfit',
  STRENGTH: 'strength', HYROX: 'hyrox', CROSSFIT: 'crossfit',
}

export function toActivityType(primary: string): ActivityType {
  return TYPE_MAP[(primary || '').toUpperCase()] || 'run'
}

function paceFrom(distanceM: number, durationS: number): string {
  if (!distanceM || !durationS) return '—'
  const secPerKm = durationS / (distanceM / 1000)
  return `${Math.floor(secPerKm / 60)}:${String(Math.round(secPerKm % 60)).padStart(2, '0')}`
}

/** Atividade da API -> card de treino da UI. */
export function toWorkoutSession(a: Activity): WorkoutSession {
  return {
    id: a.activity_id,
    type: toActivityType(a.primary_type),
    name: a.activity_name,
    distance_km: Math.round((a.distance_m || 0) / 100) / 10,
    duration_min: Math.round((a.duration_s || 0) / 60),
    pace: paceFrom(a.distance_m, a.duration_s),
    avg_hr: a.avg_hr ?? 0,
    cadence: a.avg_cadence ?? 0,
    calories: a.calories ?? 0,
    elevation_gain: a.total_elevation_gain ?? 0,
    date: a.start_time,
  }
}

const ACWR_STATUS: Record<string, AcwrStatus> = {
  destreino: 'low', aquecendo: 'low',
  'zona segura': 'optimal',
  atencao: 'high', 'atenção': 'high',
  'risco de lesao': 'very_high', 'risco de lesão': 'very_high',
}

export function toAcwrStatus(status: string): AcwrStatus {
  return ACWR_STATUS[(status || '').toLowerCase()] || 'optimal'
}

/** Estado de carga mais recente (o "hoje" do atleta). */
export function latestAcwr(items: TrainingLoadItem[]): { acwr: number; status: AcwrStatus } | null {
  if (!items?.length) return null
  const last = items[items.length - 1]
  return { acwr: last.acwr ?? 0, status: toAcwrStatus(String(last.status)) }
}

// ---- Detalhe do treino (zonas / durabilidade / track) ----

export interface ZoneBar { label: string; pct: number; loFrac: number }

/** Zonas de FC reais -> barras p/ a UI. loFrac = limite inferior ÷ FCmax (a UI escolhe a cor). */
export function toZoneBars(detail: ApiActivityDetail): ZoneBar[] {
  const { zones, hr_max } = detail.hr_zones || { zones: [], hr_max: null }
  if (!zones?.length || !hr_max) return []
  return zones.map(z => {
    const lo = z.faixa.startsWith('<') ? 0
      : z.faixa.startsWith('>') ? Number(z.faixa.slice(1))
      : Number(z.faixa.split('-')[0])
    return { label: `${z.faixa} bpm`, pct: z.pct, loFrac: lo / hr_max }
  })
}

export interface DurabilityUi { decoupling_pct: number; first_half_pa: number; second_half_pa: number; label: string }

/** Durabilidade do backend (eff_first/eff_second) -> shape da UI. null se não aplicável. */
export function toDurability(detail: ApiActivityDetail): DurabilityUi | null {
  const d = detail.durability
  if (!d?.applicable || d.decoupling_pct == null) return null
  return {
    decoupling_pct: d.decoupling_pct,
    first_half_pa: d.eff_first ?? 0,
    second_half_pa: d.eff_second ?? 0,
    label: d.label ?? '',
  }
}

/** Track (listas paralelas) -> pontos {lat, lon, cadence} p/ o mapa. [] = sem GPS (indoor). */
export function toRoutePoints(track: ApiTrack): Array<{ lat: number; lon: number; cadence: number }> {
  const { latitude, longitude } = track?.smooth ?? { latitude: [], longitude: [] }
  return latitude.map((lat, i) => ({
    lat, lon: longitude[i], cadence: track.cadence[i] ?? 0,
  }))
}
