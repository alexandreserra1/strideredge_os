// Consumo do veredito em STREAMING (SSE via fetch — EventSource não dá abort limpo).
// O texto nasce token a token; se a guarda de aterramento reprovar, o backend manda
// 'replace' com a versão corrigida; 'done' traz o estruturado (e já ficou cacheado).
import { useCallback, useRef, useState } from 'react'
import type { CoachVerdict } from '../types'

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

async function readSSE(res: Response, onEvent: (event: string, data: any) => void) {
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let sep
    while ((sep = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, sep)
      buf = buf.slice(sep + 2)
      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7).trim()
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (data) onEvent(event, JSON.parse(data))
    }
  }
}

export function useCoachStream() {
  const [text, setText] = useState('')
  const [data, setData] = useState<CoachVerdict | null>(null)
  const [isStreaming, setStreaming] = useState(false)
  const [isCorrecting, setCorrecting] = useState(false)
  const [isError, setError] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(async (id: string, force = false) => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setText(''); setData(null); setError(false); setCorrecting(false); setStreaming(true)
    try {
      const res = await fetch(
        `${BASE_URL}/activities/${id}/coach/stream${force ? '?force=true' : ''}`,
        { signal: ctrl.signal },
      )
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      await readSSE(res, (event, payload) => {
        if (event === 'token') setText(t => t + payload.text)
        else if (event === 'correcting') setCorrecting(true)
        else if (event === 'replace') { setText(payload.text); setCorrecting(false) }
        else if (event === 'done') setData(payload)
      })
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError(true)
    } finally {
      setStreaming(false); setCorrecting(false)
    }
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setText(''); setData(null); setError(false); setStreaming(false); setCorrecting(false)
  }, [])

  return { text, data, isStreaming, isCorrecting, isError, start, reset }
}
