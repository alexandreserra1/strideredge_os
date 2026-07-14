// ---- Análise de Forma por vídeo (stride-vision) ----

export interface FormMetrics {
  frames: number
  fps: number
  detection_rate_pct: number
  cadence_spm: number | null
  cadence_left: number | null
  cadence_right: number | null
  asymmetry_pct: number | null
  vertical_oscillation_pct: number | null
  knee_contact_deg: number | null
  hip_contact_deg: number | null
  trunk_lean_deg: number | null
  ground_contact_ms: number | null
  flight_ms: number | null
  foot_strike: string | null
  reliable: boolean
  quality_note: string | null
}

export interface FormAnalysis {
  analysis_id: string
  activity_id: string | null
  status: 'processing' | 'done' | 'failed'
  video_path: string | null
  metrics: FormMetrics | null
  error: string | null
  created_at: string
  modality?: string
}

// Algoritmo corretivo: desvios (medido × ideal) + plano com exercícios citados
export interface FormDeviation {
  metric: string
  label: string
  value: number
  lo: number
  hi: number
  unit: string
  side: 'baixo' | 'alto'
  source: string
  plain: string        // explicação em linguagem simples do que o desvio significa
}

export interface FormPlan {
  analysis_id: string
  verdict: string
  actions: string[]        // exercícios/ajustes gerados pelo coach (citados)
  citations: string[]
  deviations: FormDeviation[]   // o que corrigir — determinístico (medido × ideal)
}

export interface AthleteProfile {
  height_cm?: number | null
  weight_kg?: number | null
  years_running?: number | null
  goal?: string | null
}

// ---- Auth ----

export interface AuthUser { user_id: string; name: string; email: string }
export interface AuthResponse { token: string; user: AuthUser }
