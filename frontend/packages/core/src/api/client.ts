import type {
  AuthResponse,
  AuthUser,
  FormAnalysis,
  FormPlan,
  AthleteProfile,
  InjuryReport,
  InjuryTaxonomy,
  OstrcAnswers,
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

// Sessão: token guardado pelo app (localStorage) e anexado em toda chamada
const TOKEN_KEY = 'se_token'
export const session = {
  get: () => (typeof localStorage !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
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
    get: (id: string) => request<FormAnalysis>(`/form/${id}`),
    // multipart: fetch próprio (o request() força JSON)
    upload: async (file: File, opts?: { modality?: string; view?: string }) => {
      const fd = new FormData()
      fd.append('video', file)
      fd.append('modality', opts?.modality ?? 'run')
      fd.append('view', opts?.view ?? 'lateral')   // lateral (sagital) | frontal (queda pélvica, valgo)
      const token = session.get()
      const res = await fetch(`${BASE_URL}/form`, {
        method: 'POST', body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })
      if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => ''))
      return res.json() as Promise<{ analysis_id: string; status: string }>
    },
    videoUrl: (id: string) => `${BASE_URL}/form/${id}/video`,
    coach: (id: string) => request<FormPlan>(`/form/${id}/coach`, { method: 'POST' }),
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
  },
}
