import { useState } from 'react'
import { Footprints, Dumbbell, Boxes, Lock, Clapperboard } from 'lucide-react'
import FormAnalysisCard from '../components/ui/FormAnalysis'

// Seletor de modalidade. Só Corrida funciona hoje (o motor é de corrida); Hyrox/CrossFit
// ficam travados "em breve" — a página já nasce pronta pra receber os motores depois.
const MODALITIES = [
  { id: 'run', label: 'Corrida', icon: Footprints, ready: true },
  { id: 'hyrox', label: 'Hyrox', icon: Boxes, ready: false },
  { id: 'crossfit', label: 'CrossFit', icon: Dumbbell, ready: false },
] as const

export default function MovementAnalysis({ onNavigate }: { onNavigate: (r: string) => void }) {
  const [modality, setModality] = useState<'run' | 'hyrox' | 'crossfit'>('run')
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
        <FormAnalysisCard />
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
        <button onClick={() => onNavigate('landing')} className="text-brand">Sobre o app</button>
      </p>
    </div>
  )
}
