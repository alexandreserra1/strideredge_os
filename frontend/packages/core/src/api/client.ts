import type {
  AuthResponse,
  AuthUser,
  FormAnalysis,
  Activity,
  ApiActivityDetail,
  ApiTrack,
  TelemetryPoint,
  CadenceSpectrum,
  CoachVerdict,
  TrainingLoadItem,
  ApiFitness,
  AskResponse,
} from '../types'

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
  activities: {
    list: () => request<Activity[]>('/activities'),
    detail: (id: string) => request<ApiActivityDetail>(`/activities/${id}`),
    track: (id: string) => request<ApiTrack>(`/activities/${id}/track`),
    telemetry: (id: string) => request<TelemetryPoint[]>(`/activities/${id}/telemetry`),
    spectrum: (id: string) => request<CadenceSpectrum>(`/activities/${id}/cadence-spectrum`),
    coach: (id: string) =>
      request<CoachVerdict>(`/activities/${id}/coach`, { method: 'POST' }),
  },
  form: {
    list: (activityId?: string) =>
      request<FormAnalysis[]>(`/form${activityId ? `?activity_id=${activityId}` : ''}`),
    get: (id: string) => request<FormAnalysis>(`/form/${id}`),
    // multipart: fetch próprio (o request() força JSON)
    upload: async (file: File, activityId?: string) => {
      const fd = new FormData()
      fd.append('video', file)
      if (activityId) fd.append('activity_id', activityId)
      const token = session.get()
      const res = await fetch(`${BASE_URL}/form`, {
        method: 'POST', body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })
      if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => ''))
      return res.json() as Promise<{ analysis_id: string; status: string }>
    },
    videoUrl: (id: string) => `${BASE_URL}/form/${id}/video`,
  },
  trainingLoad: {
    list: () => request<TrainingLoadItem[]>('/training-load'),
  },
  fitness: {
    get: () => request<ApiFitness>('/fitness'),
  },
  ask: (question: string) =>
    request<AskResponse>('/ask', {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),
}
