import type {
  AuthResponse,
  AuthUser,
  CorrectivePlan,
  FormAnalysis,
  FormProgress,
  FormPlan,
  AthleteProfile,
  InjuryReport,
  InjuryRetrospective,
  InjuryTaxonomy,
  OstrcAnswers,
  PlanResponse,
  PlanRecord,
  ShoeRecommendation,
} from '../types'

// Payload do log de lesão: taxonomia + OSTRC (tudo opcional no contrato; o form valida forte)
export interface InjuryLogInput extends OstrcAnswers {
  region?: string | null
  diagnosis?: string | null
  side?: string | null
  onset_date?: string | null
  notes?: string | null
  symptom_text?: string | null
}

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

// Sessão: bearer só vive na aba atual; reduz exposição em computador compartilhado/XSS persistente.
const TOKEN_KEY = 'se_token'
export const session = {
  get: () => (typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(TOKEN_KEY) : null),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
}

const ANALYSIS_ACCESS_KEY = 'se_analysis_access'
const LAST_ANALYSIS_KEY = 'se_last_analysis'
type AnalysisAccess = Record<string, string>

const analysisAccess = {
  get: (id: string) => {
    try {
      const raw = sessionStorage.getItem(ANALYSIS_ACCESS_KEY)
      return raw ? (JSON.parse(raw) as AnalysisAccess)[id] ?? null : null
    } catch { return null }
  },
  set: (id: string, token: string) => {
    const raw = sessionStorage.getItem(ANALYSIS_ACCESS_KEY)
    const all = raw ? JSON.parse(raw) as AnalysisAccess : {}
    all[id] = token
    sessionStorage.setItem(ANALYSIS_ACCESS_KEY, JSON.stringify(all))
    sessionStorage.setItem(LAST_ANALYSIS_KEY, id)
  },
  lastId: () => sessionStorage.getItem(LAST_ANALYSIS_KEY),
}

function analysisHeaders(id: string): HeadersInit {
  const capability = analysisAccess.get(id)
  return capability ? { 'X-Analysis-Token': capability } : {}
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const token = session.get()
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new ApiError(res.status, text)
  }
  return res.json()
}

export const api = {
  auth: {
    register: (name: string, email: string, password: string) =>
      request<AuthResponse>('/auth/register', { method: 'POST', body: JSON.stringify({ name, email, password }) }),
    login: (email: string, password: string) =>
      request<AuthResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
    google: (credential: string) =>
      request<AuthResponse>('/auth/google', { method: 'POST', body: JSON.stringify({ credential }) }),
    me: () => request<AuthUser>('/auth/me'),
  },
  form: {
    list: () => request<FormAnalysis[]>('/form'),
    progress: () => request<FormProgress>('/form/progress'),
    get: (id: string) => request<FormAnalysis>(`/form/${id}`, { headers: analysisHeaders(id) }),
    // multipart: fetch próprio (o request() força JSON)
    upload: async (file: File, opts?: { modality?: string; view?: string; videoFrontal?: File }) => {
      const fd = new FormData()
      fd.append('video', file)
      fd.append('modality', opts?.modality ?? 'run')
      fd.append('view', opts?.view ?? 'lateral')   // lateral (sagital) | frontal (queda pélvica, valgo)
      if (opts?.videoFrontal) fd.append('video_frontal', opts.videoFrontal)
      const token = session.get()
      const res = await fetch(`${BASE_URL}/form`, {
        method: 'POST', body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })
      if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => ''))
      const out = await res.json() as { analysis_id: string; status: string; access_token?: string }
      if (out.access_token) analysisAccess.set(out.analysis_id, out.access_token)
      return out
    },
    lastGuestAnalysisId: () => analysisAccess.lastId(),
    video: async (id: string) => {
      const token = session.get()
      const res = await fetch(`${BASE_URL}/form/${id}/video`, {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...analysisHeaders(id) },
      })
      if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => ''))
      return URL.createObjectURL(await res.blob())
    },
    coach: (id: string) => request<FormPlan>(`/form/${id}/coach`, { method: 'POST', headers: analysisHeaders(id) }),
    // Plano corretivo de N semanas (faseado, citado) a partir da análise.
    // A rota devolve o plano ANINHADO sob `plan` ({analysis_id, plan:{...}}); aqui achatamos pro
    // shape que a UI consome (PlanResponse = CorrectivePlan & {analysis_id}). Sem isso, o componente
    // lê plan.priority/plan.weeks no topo -> undefined.length -> TypeError -> tela preta.
    plan: async (id: string, weeks: number): Promise<PlanResponse> => {
      const r = await request<{ analysis_id: string; plan: CorrectivePlan }>(
        `/form/${id}/plan?weeks=${weeks}`, { method: 'POST', headers: analysisHeaders(id) })
      return { ...r.plan, analysis_id: r.analysis_id }
    },
    // Recomendação de tênis honesta (pisada + oscilação + perfil + histórico)
    shoe: (id: string) => request<ShoeRecommendation>(`/form/${id}/shoe`, { method: 'POST', headers: analysisHeaders(id) }),
  },
  plans: {
    list: () => request<PlanRecord[]>('/plans'),
  },
  profile: {
    get: () => request<AthleteProfile>('/profile'),
    save: (p: AthleteProfile) =>
      request<AthleteProfile>('/profile', { method: 'PUT', body: JSON.stringify(p) }),
  },
  injuries: {
    taxonomy: () => request<InjuryTaxonomy>('/injuries/taxonomy'),
    list: () => request<InjuryReport[]>('/injuries'),
    log: (report: InjuryLogInput) =>
      request<InjuryReport>('/injuries', { method: 'POST', body: JSON.stringify(report) }),
    // Cruza a lesão com os sinais biomecânicos das análises ANTES do onset (associação citada).
    retrospective: (id: string) =>
      request<InjuryRetrospective>(`/injuries/${id}/retrospective`),
  },
}
