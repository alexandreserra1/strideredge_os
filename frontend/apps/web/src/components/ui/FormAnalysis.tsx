import { useCallback, useEffect, useRef, useState } from 'react'
import { Clapperboard, Info, Loader2, Upload } from 'lucide-react'
import { api } from '@strideredge/core'
import type { FormAnalysis as Analysis } from '@strideredge/core'

// Semáforo por métrica (faixas da literatura de corrida; explicação vai junto — didático)
const METRIC_DEFS = [
  {
    key: 'cadence_spm' as const, label: 'Cadência', unit: 'spm',
    level: (v: number) => (v >= 170 ? 'ok' : v >= 160 ? 'warn' : 'risk'),
    why: 'Passos por minuto medidos PELA CÂMERA. Alvo ≥170; abaixo de 160 aumenta a carga de impacto por passo.',
  },
  {
    key: 'asymmetry_pct' as const, label: 'Assimetria E/D', unit: '%',
    level: (v: number) => (v < 10 ? 'ok' : v < 20 ? 'warn' : 'risk'),
    why: 'Diferença de amplitude entre as pernas. <10% é normal; acima disso, um lado trabalha mais — fadiga ou compensação.',
  },
  {
    key: 'vertical_oscillation_pct' as const, label: 'Oscilação vertical', unit: '% da perna',
    level: (v: number) => (v < 8 ? 'ok' : v < 12 ? 'warn' : 'risk'),
    why: 'Quanto o quadril sobe e desce. Menos oscilação = energia indo pra FRENTE, não pra cima.',
  },
]
const LEVEL_COLOR: Record<string, string> = { ok: '#34D399', warn: '#FBBF24', risk: '#F87171' }

export default function FormAnalysisCard({ activityId, watchCadence }: {
  activityId: string
  watchCadence?: number          // cadência do relógio (comparação câmera vs Garmin)
}) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  // última análise deste treino
  useEffect(() => {
    setAnalysis(null)
    api.form.list(activityId).then(list => setAnalysis(list[0] ?? null)).catch(() => {})
  }, [activityId])

  // enquanto processa, consulta a cada 3s
  useEffect(() => {
    if (analysis?.status !== 'processing') return
    const t = setInterval(() => {
      api.form.get(analysis.analysis_id).then(setAnalysis).catch(() => {})
    }, 3000)
    return () => clearInterval(t)
  }, [analysis?.status, analysis?.analysis_id])

  const onFile = useCallback(async (file: File) => {
    setError('')
    setUploading(true)
    try {
      const out = await api.form.upload(file, activityId)
      setAnalysis({ analysis_id: out.analysis_id, activity_id: activityId, status: 'processing',
                    video_path: null, metrics: null, error: null, created_at: '' })
    } catch {
      setError('Falha no upload — a API está no ar?')
    } finally {
      setUploading(false)
    }
  }, [activityId])

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Clapperboard size={14} className="text-brand" /> Análise de Forma
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-brand/12 text-brand">beta</span>
        </h3>
        {analysis?.status === 'done' && (
          <button onClick={() => fileRef.current?.click()} className="btn-ghost text-xs">Nova análise</button>
        )}
      </div>

      <input ref={fileRef} type="file" accept="video/*" className="hidden"
        onChange={e => e.target.files?.[0] && onFile(e.target.files[0])} />

      {!analysis && (
        <button onClick={() => fileRef.current?.click()} disabled={uploading}
          className="w-full rounded-xl border-2 border-dashed border-border-medium hover:border-brand/50 transition-colors p-8 text-center">
          <Upload size={22} className="mx-auto text-text-secondary mb-2" />
          <p className="text-sm font-medium">{uploading ? 'Enviando…' : 'Enviar vídeo do treino'}</p>
          <p className="text-xs text-text-muted mt-1">
            Filme de LADO, corpo inteiro no quadro, 20–30s (esteira funciona ótimo).
            A IA desenha seu esqueleto e mede cadência, assimetria e oscilação — 100% local.
          </p>
        </button>
      )}

      {analysis?.status === 'processing' && (
        <div className="flex items-center gap-3 p-5 rounded-xl bg-brand/[0.06] border border-brand/20">
          <Loader2 size={18} className="text-brand animate-spin" />
          <div>
            <p className="text-sm font-medium">Analisando seu movimento…</p>
            <p className="text-xs text-text-secondary">Pose estimation frame a frame no motor local (~1 min).</p>
          </div>
        </div>
      )}

      {analysis?.status === 'failed' && (
        <div className="p-4 rounded-xl bg-accent-red/10 border border-accent-red/20">
          <p className="text-sm text-accent-red">Não consegui analisar: {analysis.error}</p>
          <button onClick={() => fileRef.current?.click()} className="btn-ghost text-xs mt-2">Tentar outro vídeo</button>
        </div>
      )}

      {analysis?.status === 'done' && analysis.metrics && (
        <div className="grid lg:grid-cols-2 gap-4 animate-fade-in">
          {/* o vídeo da IA vendo o movimento */}
          <video controls loop muted playsInline className="w-full rounded-xl border border-border-light bg-black"
            src={api.form.videoUrl(analysis.analysis_id)} />

          <div className="space-y-3">
            {METRIC_DEFS.map(def => {
              const v = analysis.metrics![def.key]
              if (v == null) return null
              const lv = def.level(v)
              return (
                <div key={def.key} className="rounded-xl bg-surface-200 border border-border-light p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-text-secondary">{def.label}</p>
                    <span className="text-sm font-bold tabular-nums" style={{ color: LEVEL_COLOR[lv] }}>
                      {Math.round(v * 10) / 10} <span className="text-[10px] font-medium">{def.unit}</span>
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted mt-1 leading-snug">{def.why}</p>
                  {def.key === 'cadence_spm' && watchCadence ? (
                    <p className="text-[11px] mt-1 text-brand">
                      Relógio marcou {watchCadence} spm — diferença de {Math.abs(v - watchCadence).toFixed(0)} spm (validação câmera×Garmin).
                    </p>
                  ) : null}
                </div>
              )
            })}
            <p className="text-[10px] text-text-muted flex items-center gap-1">
              <Info size={10} /> Qualidade da detecção: {Math.round(analysis.metrics.detection_rate_pct)}% dos frames
            </p>
          </div>
        </div>
      )}

      {error && <p className="text-xs text-accent-red mt-3">{error}</p>}
    </div>
  )
}
