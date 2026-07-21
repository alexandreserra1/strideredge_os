import { useCallback, useState } from 'react'
import { AlertTriangle, Footprints, Loader2 } from 'lucide-react'
import { api } from '@strideredge/core'
import type { ShoeRecommendation } from '@strideredge/core'
import InfoHint from './InfoHint'

/**
 * Bloco de TÊNIS dentro da análise. Puxa `api.form.shoe(id)` — recomendação honesta e citada
 * (amortecimento, faixa de drop, dicas, fontes). O `caveat` de honestidade é OBRIGATÓRIO e vai
 * em destaque: a pisada é INFERÊNCIA do vídeo e nenhum tênis previne lesão sozinho.
 */
export default function ShoeBlock({ analysisId }: { analysisId: string }) {
  const [rec, setRec] = useState<ShoeRecommendation | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const generate = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setRec(await api.form.shoe(analysisId))
    } catch {
      setError('Não consegui montar a recomendação — a API está no ar?')
    } finally {
      setLoading(false)
    }
  }, [analysisId])

  return (
    <div className="mt-4 pt-4 border-t border-border-light">
      <h4 className="text-sm font-semibold flex items-center gap-1.5 mb-3">
        <Footprints size={15} className="text-brand" /> Que tipo de tênis combina com você
        <InfoHint text="A partir da sua pisada estimada, oscilação vertical, peso e histórico, sugerimos uma FAIXA de amortecimento e drop — sempre citada. Não é uma marca; é um ajuste de carga." />
      </h4>

      {!rec && (
        <button onClick={generate} disabled={loading} className="btn-primary text-sm w-full">
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 size={15} className="animate-spin" /> Analisando…
            </span>
          ) : 'Ver recomendação de tênis'}
        </button>
      )}

      {error && <p className="text-xs text-accent-red mt-2">{error}</p>}

      {rec && (
        <div className="space-y-3 animate-fade-in">
          {rec.cover && (
            <p className="text-sm text-text-secondary leading-relaxed">{rec.cover}</p>
          )}

          {/* Amortecimento + faixa de drop */}
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-border-light bg-surface-200 p-3">
              <p className="text-[10px] text-text-muted uppercase tracking-wider">Amortecimento</p>
              <p className="text-xs font-semibold text-text-primary mt-1 leading-snug">{rec.cushioning}</p>
            </div>
            <div className="rounded-xl border border-border-light bg-surface-200 p-3">
              <p className="text-[10px] text-text-muted uppercase tracking-wider">Drop (calcanhar↔ponta)</p>
              <p className="text-xs font-semibold text-text-primary mt-1 leading-snug">{rec.drop_mm} mm</p>
            </div>
          </div>

          {/* Dicas */}
          {rec.tips.length > 0 && (
            <ul className="space-y-1.5">
              {rec.tips.map((t, i) => (
                <li key={i} className="text-xs text-text-secondary flex items-start gap-2 leading-snug">
                  <span className="text-brand mt-0.5 shrink-0">→</span>{t}
                </li>
              ))}
            </ul>
          )}

          {/* Caveat de HONESTIDADE — obrigatório, em destaque */}
          <div className="rounded-xl bg-accent-yellow/10 border border-accent-yellow/30 p-3">
            <p className="text-[11px] font-semibold text-accent-yellow flex items-center gap-1.5 mb-1">
              <AlertTriangle size={13} /> Leia com honestidade
            </p>
            <p className="text-[11px] text-text-secondary leading-snug">{rec.caveat}</p>
          </div>

          {/* Fontes citadas */}
          {rec.sources.length > 0 && (
            <div>
              <p className="text-[10px] text-text-muted mb-1">Baseado em:</p>
              <div className="flex flex-wrap gap-1.5">
                {rec.sources.map((s, i) => (
                  <span key={i} title={s}
                    className="text-[10px] text-text-secondary bg-surface-200 border border-border-light px-2 py-0.5 rounded-full">
                    📚 {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
