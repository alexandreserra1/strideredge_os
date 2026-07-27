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
  // Proveniência: ângulos produtivos vêm da imagem 2D; world-3D só existe em dumps diagnósticos.
  joint_angle_space?: 'image_2d'
  trunk_lean_deg: number | null
  ground_contact_ms: number | null
  flight_ms: number | null
  ground_contact_source?: 'heel_toe_landmarks' | 'heel_toe_with_ankle_fallback' | 'ankle_proxy' | null
  foot_landmark_coverage_pct?: number | null
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
  metrics: FormMetrics | null
  error: string | null
  created_at: string
  modality?: string
}

export interface FormMetricProgress {
  metric: string
  label: string
  unit: string
  baseline: number
  current: number
  delta: number
  baseline_samples: number
  current_samples: number
}

export interface FormProgress {
  status: 'ok' | 'insufficient_history'
  comparable_analyses: number
  excluded_incompatible: number
  signature: { view: string; backend: string; model_version: string; joint_angle_space: string } | null
  metrics: FormMetricProgress[]
  caveat: string
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
  how_to_measure?: string   // como o atleta confere isso sozinho (determinístico)
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

export interface UncertainMetric {
  metric: string       // mesma chave de FormMetrics
  label: string
  reason?: string      // por que não deu pra avaliar (baixa confiança | valor implausível)
}

export interface FormPlan {
  analysis_id: string
  verdict: string
  actions: string[]        // exercícios/ajustes gerados pelo coach (citados)
  citations: string[]
  deviations: FormDeviation[]   // o que corrigir — determinístico (medido × ideal)
  risk?: InjuryRisk        // faixa de risco relativa (aterrada, citada)
  // métricas que o coach NÃO pôde avaliar com confiança (baixa confiabilidade OU valor
  // implausível anulado). A métrica CONTINUA aparecendo na tela, só ganha um selo com o motivo.
  uncertain_metrics?: UncertainMetric[]
}

// Plano corretivo faseado (analytics/training_plan.py) — POR FASE, não por semana (explicativo, sem
// repetir o exercício toda semana). Cada fase: título + janela de semanas + porquê + exercícios.
export interface PlanExercise {
  exercise: string
  how?: string           // como executar + se auto-conferir
  progression?: string   // o que muda ao longo das semanas (dose progressiva)
  source: string
}

export interface PlanPhase {
  key: string            // 'base' | 'forca' | 'drill_de_marcha'
  title: string          // rótulo humano (ex.: 'Força — fortalecer')
  weeks_label: string    // ex.: 'Semanas 1–3'
  why: string            // por que esta fase, nesta ordem
  focus: string
  exercises: PlanExercise[]
}

export interface CorrectivePlan {
  duration_weeks: number
  priority: { metric: string; label: string }[]
  intro?: string
  phases: PlanPhase[]
  caveat: string
  unreliable?: boolean   // captura ruim -> sem plano, só o aviso de refilmar
  cover?: string         // capa humana opcional (LLM)
}

// a rota espalha o plano no topo (`{analysis_id, ...plan}`), não aninha sob `plan`
export type PlanResponse = CorrectivePlan & { analysis_id: string }

// Registro persistido de plano gerado (GET /plans — histórico/progressão)
export interface PlanRecord {
  id: string
  user_id: string
  analysis_id: string | null
  weeks: number | null
  plan: CorrectivePlan | null
  created_at: string
}

// Recomendação de tênis HONESTA e citada (analytics/shoe.py)
export interface ShoeRecommendation {
  analysis_id: string
  cushioning: string
  drop_mm: string        // faixa, ex.: "4-6" ou "8-10 (migrando para menor)"
  tips: string[]
  caveat: string         // OBRIGATÓRIO: pisada é inferência; tênis não previne lesão sozinho
  sources: string[]
  cover?: string         // capa humana opcional (LLM)
}

export interface AthleteProfile {
  height_cm?: number | null
  weight_kg?: number | null
  years_running?: number | null
  goal?: string | null
  // metas de treino/tênis (EPIC B) — alimentam o plano corretivo e a recomendação de tênis
  goal_timeframe_weeks?: number | null   // "em quanto tempo quero melhorar"
  weekly_volume_km?: number | null
  days_per_week?: number | null
  current_shoe?: string | null
  footstrike_pref?: string | null        // calcanhar | medio | antepe
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
  diagnosis: string | null      // NULL até o LLM mapear symptom_text num termo da taxonomia (coach-time)
  side: string | null
  onset_date: string | null
  notes: string | null
  symptom_text: string | null   // texto livre: o que o atleta sente / laudo do médico (contexto p/ coach)
  reported_at: string
  severity: number     // 0–100, computada na leitura
}

// ---- Auth ----

export interface AuthUser { user_id: string; name: string; email: string }
export interface AuthResponse { token: string; user: AuthUser }
