import type {
  Activity,
  ActivityDetail,
  TrackData,
  TelemetryPoint,
  CadenceSpectrum,
  CoachVerdict,
  TrainingLoadItem,
  FitnessData,
  AskResponse,
} from '../types'

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new ApiError(res.status, text)
  }
  return res.json()
}

export const api = {
  activities: {
    list: () => request<Activity[]>('/activities'),
    detail: (id: string) => request<ActivityDetail>(`/activities/${id}`),
    track: (id: string) => request<TrackData>(`/activities/${id}/track`),
    telemetry: (id: string) => request<TelemetryPoint[]>(`/activities/${id}/telemetry`),
    spectrum: (id: string) => request<CadenceSpectrum>(`/activities/${id}/cadence-spectrum`),
    coach: (id: string) =>
      request<CoachVerdict>(`/activities/${id}/coach`, { method: 'POST' }),
  },
  trainingLoad: {
    list: () => request<TrainingLoadItem[]>('/training-load'),
  },
  fitness: {
    get: () => request<FitnessData>('/fitness'),
  },
  ask: (question: string) =>
    request<AskResponse>('/ask', {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),
}
