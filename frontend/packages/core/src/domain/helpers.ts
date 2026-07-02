export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h${m.toString().padStart(2, '0')}`
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function formatPace(secondsPerKm: number): string {
  const m = Math.floor(secondsPerKm / 60)
  const s = Math.round(secondsPerKm % 60)
  return `${m}:${s.toString().padStart(2, '0')}/km`
}

export function msToPace(speedMs: number): string {
  if (!speedMs || speedMs <= 0) return '—'
  const pace = 1000 / speedMs
  return formatPace(pace)
}

export function formatDistance(meters: number): string {
  if (meters >= 1000) return `${(meters / 1000).toFixed(2)} km`
  return `${meters} m`
}

export function metersToKm(meters: number): number {
  return Math.round(meters / 10) / 100
}

export function paceToSpeedMs(paceSecPerKm: number): number {
  return 1000 / paceSecPerKm
}

export function dateFromISO(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: 'numeric', month: 'short' })
}

export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

export function dayName(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { weekday: 'short' })
}
