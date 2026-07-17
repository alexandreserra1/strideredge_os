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
  // plano frontal (vista frontal)
  pelvic_drop_deg?: number | null
  knee_valgus_deg?: number | null
  view?: string | null            // 'lateral' | 'frontal'
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

// Risco de lesão — score RELATIVO aterrado na literatura (não é probabilidade)
export interface RiskFactor {
  metric: string
  label: string
  value: number
  unit: string
  source: string
  plain: string
  weight: number
  contribution: number
}

export interface InjuryRisk {
  risk_band: 'baixo' | 'moderado' | 'elevado' | 'alto'
  score: number
  factors: RiskFactor[]      // o que puxou o risco, do maior pro menor
  model: string              // 'literatura' | 'treinado'
  caveat: string
}

export interface FormPlan {
  analysis_id: string
  verdict: string
  actions: string[]        // exercícios/ajustes gerados pelo coach (citados)
  citations: string[]
  deviations: FormDeviation[]   // o que corrigir — determinístico (medido × ideal)
  risk?: InjuryRisk        // faixa de risco relativa (aterrada, citada)
}

export interface AthleteProfile {
  height_cm?: number | null
  weight_kg?: number | null
  years_running?: number | null
  goal?: string | null
}

// ---- Lesões (log OSTRC — fonte do dataset de risco) ----

export interface InjuryDiagnosis {
  id: string
  label: string
  region: string
  is_mapped: boolean   // false = logável, mas sem análise biomecânica citável ainda
}

export interface InjuryTaxonomy {
  regions: string[]
  sides: string[]
  diagnoses: InjuryDiagnosis[]
}

// As 4 respostas OSTRC (0–3 cada). Enviadas no log; severidade 0–100 vem computada na leitura.
export interface OstrcAnswers {
  q_participation?: number | null
  q_volume?: number | null
  q_performance?: number | null
  q_pain?: number | null
}

export interface InjuryReport extends OstrcAnswers {
  id: string
  region: string | null
  diagnosis: string | null
  side: string | null
  onset_date: string | null
  notes: string | null
  reported_at: string
  severity: number     // 0–100, computada na leitura
}

// ---- Auth ----

export interface AuthUser { user_id: string; name: string; email: string }
export interface AuthResponse { token: string; user: AuthUser }
