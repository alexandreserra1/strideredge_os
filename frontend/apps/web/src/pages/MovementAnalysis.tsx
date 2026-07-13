import { useState } from 'react'
import { Footprints, Dumbbell, Boxes, Lock, Clapperboard, Link2 } from 'lucide-react'
import FormAnalysisCard from '../components/ui/FormAnalysis'
import { useActivities } from '@strideredge/core'

// Seletor de modalidade. Só Corrida funciona hoje (o motor é de corrida); Hyrox/CrossFit
// ficam travados "em breve" — a página já nasce pronta pra receber os motores depois.
const MODALITIES = [
  { id: 'run', label: 'Corrida', icon: Footprints, ready: true },
  { id: 'hyrox', label: 'Hyrox', icon: Boxes, ready: false },
  { id: 'crossfit', label: 'CrossFit', icon: Dumbbell, ready: false },
] as const

export default function MovementAnalysis({ onNavigate }: { onNavigate: (r: string) => void }) {
  const [modality, setModality] = useState<'run' | 'hyrox' | 'crossfit'>('run')
  const [linkedId, setLinkedId] = useState<string>('')   // '' = análise avulsa

  // corridas reais pra oferecer o vínculo opcional (habilita câmera × Garmin)
  const { data: acts } = useActivities()
  const runs = (acts ?? []).filter(a => String(a.primary_type).toUpperCase() === 'RUN')
  const linked = runs.find(a => a.activity_id === linkedId)
  const active = MODALITIES.find(m => m.id === modality)!

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight flex items-center gap-2">
          <Clapperboard size={24} className="text-brand" /> Análise de Forma
        </h1>
        <p className="text-text-secondary mt-1">
          A IA vê o seu movimento e traduz em causa-raiz — 100% no seu aparelho.
        </p>
      </div>

      {/* Seletor de modalidade */}
      <div className="grid grid-cols-3 gap-2">
        {MODALITIES.map(({ id, label, icon: Icon, ready }) => {
          const on = modality === id
          return (
            <button key={id} disabled={!ready} onClick={() => ready && setModality(id)}
              className={`relative rounded-xl border p-3 text-center transition-colors ${
                on ? 'border-brand bg-brand/10' : 'border-border-light hover:border-border-medium'
              } ${!ready ? 'opacity-55 cursor-not-allowed' : ''}`}>
              <Icon size={20} className={`mx-auto mb-1 ${on ? 'text-brand' : 'text-text-secondary'}`} />
              <p className="text-xs font-medium">{label}</p>
              {!ready && (
                <span className="absolute top-1.5 right-1.5 flex items-center gap-0.5 text-[9px] text-text-muted">
                  <Lock size={9} /> em breve
                </span>
              )}
            </button>
          )
        })}
      </div>

      {active.ready ? (
        <>
          {/* Vínculo OPCIONAL a um treino — a única conexão que faz sentido (valida câmera × Garmin) */}
          {runs.length > 0 && (
            <div className="card flex flex-col sm:flex-row sm:items-center gap-2">
              <label className="text-xs text-text-secondary flex items-center gap-1.5 shrink-0">
                <Link2 size={13} className="text-brand" /> Vincular a um treino (opcional)
              </label>
              <select value={linkedId} onChange={e => setLinkedId(e.target.value)}
                className="flex-1 bg-surface-200 border border-border-light rounded-lg px-3 py-1.5 text-xs">
                <option value="">Análise avulsa (só a câmera)</option>
                {runs.slice(0, 20).map(a => (
                  <option key={a.activity_id} value={a.activity_id}>
                    {a.activity_name} · {new Date(a.start_time).toLocaleDateString('pt-BR')}
                  </option>
                ))}
              </select>
              {linked && (
                <span className="text-[11px] text-brand shrink-0">
                  compara com o Garmin ({Math.round(linked.avg_cadence ?? 0)} spm)
                </span>
              )}
            </div>
          )}

          {/* remonta ao trocar o vínculo (recarrega a análise certa) */}
          <FormAnalysisCard key={linkedId || 'avulsa'}
            activityId={linked?.activity_id}
            watchCadence={linked?.avg_cadence ? Math.round(linked.avg_cadence) : undefined} />
        </>
      ) : (
        <div className="card text-center py-10">
          <Lock size={22} className="mx-auto text-text-muted mb-2" />
          <p className="text-sm font-medium">Análise de {active.label} em breve</p>
          <p className="text-xs text-text-muted mt-1 max-w-sm mx-auto">
            O motor de visão hoje é afinado pra corrida. Movimentos de {active.label} (contagem de
            repetições e forma por exercício) são o próximo passo.
          </p>
          <button onClick={() => setModality('run')} className="btn-ghost text-xs mt-3">
            Voltar pra Corrida
          </button>
        </div>
      )}

      <p className="text-[11px] text-text-muted text-center">
        Dica: filme de lado, corpo inteiro no quadro, 20–30s.{' '}
        <button onClick={() => onNavigate('dashboard')} className="text-brand">Voltar ao início</button>
      </p>
    </div>
  )
}
