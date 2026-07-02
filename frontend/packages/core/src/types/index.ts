export type FoxEmotion =
  | 'happy' | 'focused' | 'encouraging' | 'celebrating'
  | 'tired' | 'recovering' | 'sleeping' | 'surprised'

export type FoxExpression = FoxEmotion

export type ActivityType = 'run' | 'treadmill' | 'hyrox' | 'crossfit' | 'recovery' | 'strength'

export type AcwrStatus = 'low' | 'optimal' | 'high' | 'very_high'

export interface Activity {
  activity_id: string
  activity_name: string
  primary_type: ActivityType
  start_time: string
  distance_m: number
  duration_s: number
  avg_hr?: number
  avg_cadence?: number
  avg_pace?: number
  total_elevation_gain?: number
  calories?: number
}

export interface ActivityDetail extends Activity {
  max_hr?: number
  avg_pace_min_km?: string
  breaking_point?: {
    timestamp: string
    heart_rate: number
    cadence: number
  } | null
  efficiency?: {
    overall: number
    flat: number
    uphill: number
  } | null
  durability?: {
    decoupling_pct: number
    first_half_pa: number
    second_half_pa: number
  } | null
  hr_zones?: {
    zone_1: number
    zone_2: number
    zone_3: number
    zone_4: number
    zone_5: number
  } | null
}

export interface TrackPoint {
  lat: number
  lon: number
}

export interface TrackData {
  points: Array<{
    raw: TrackPoint
    smooth: TrackPoint
    cadence: number
  }>
}

export interface TelemetryPoint {
  timestamp: string
  heart_rate: number | null
  cadence: number | null
  altitude: number | null
  speed_ms: number | null
}

export interface CadenceSpectrum {
  dominant_frequency_hz: number
  spectrum: {
    frequencies: number[]
    magnitudes: number[]
  }
}

export interface CoachVerdict {
  activity_id: string
  verdict: string
  strengths?: string[]
  improvements?: string[]
  actions?: string[]
  citations?: string[]
}

export interface TrainingLoadItem {
  day: string
  daily_load: number
  acute_7d: number
  chronic_28d: number
  acwr: number
  days_of_history: number
  status: AcwrStatus
  ramp_pct: number
}

export interface RacePredictions {
  distance_m: number
  label: string
  predicted_seconds: number
  predicted_pace: string
}

export interface FitnessData {
  reference: {
    activity_id: string
    distance_m: number
    duration_s: number
  }
  predictions: Record<string, RacePredictions>
  fitness: {
    trend: 'up' | 'down' | 'stable'
    pct_change: number
    points: Array<{ day: string; efficiency: number }>
  }
}

export interface AskResponse {
  question: string
  sql: string
  rows: Record<string, unknown>[]
  answer: string
}

export interface PrescribedWorkout {
  day: string
  type: ActivityType
  name: string
  description: string
  target_pace?: string
  target_hr?: string
  duration_min: number
  distance_km?: number
}

export interface WeeklyPlan {
  week: number
  label: string
  days: PrescribedWorkout[]
}

export interface WorkoutSession {
  id: string
  type: ActivityType
  name: string
  distance_km: number
  duration_min: number
  pace: string
  avg_hr: number
  cadence: number
  calories: number
  elevation_gain: number
  date: string
  route_name?: string
}
