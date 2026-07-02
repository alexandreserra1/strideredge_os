import { useState, useEffect, useRef } from 'react'
import { Play, Pause, StopCircle, Map, Volume2 } from 'lucide-react'

const voiceCues: Array<{ time: number; text: string }> = [
  { time: 5, text: 'Respiração estável. Foco no ritmo.' },
  { time: 15, text: 'Segura o ritmo — FC acima do alvo.' },
  { time: 25, text: 'Cadência excelente, mantém!' },
  { time: 35, text: 'Metade do caminho. Força aí!' },
  { time: 45, text: 'Últimos 5 km. Hora de abrir.' },
  { time: 55, text: 'Mais 1 km! Dá tudo agora!' },
]

export default function RunMode() {
  const [status, setStatus] = useState<'idle' | 'running' | 'paused' | 'finished'>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [currentCue, setCurrentCue] = useState<string | null>(null)
  const [showCue, setShowCue] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const pace = '5:02'
  const distance = (elapsed * 0.0033).toFixed(2)
  const hr = Math.round(155 + Math.sin(elapsed * 0.1) * 8)
  const cadence = 168 + Math.round(Math.sin(elapsed * 0.05) * 4)

  useEffect(() => {
    if (status === 'running') {
      intervalRef.current = setInterval(() => {
        setElapsed(prev => {
          const next = prev + 1
          const cue = voiceCues.find(c => c.time === next)
          if (cue) {
            setCurrentCue(cue.text)
            setShowCue(true)
            setTimeout(() => setShowCue(false), 5000)
          }
          return next
        })
      }, 1000)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [status])

  const formatTime = (s: number) =>
    `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`

  const toggleRun = () => {
    if (status === 'idle') { setStatus('running'); setElapsed(0) }
    else if (status === 'running') setStatus('paused')
    else if (status === 'paused') setStatus('running')
  }

  const stopRun = () => {
    setStatus('finished')
    if (intervalRef.current) clearInterval(intervalRef.current)
  }

  if (status === 'idle') {
    return (
      <div className="max-w-2xl mx-auto space-y-8 animate-fade-in mt-12">
        <div className="text-center">
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Modo Corrida</h1>
          <p className="text-text-secondary mt-1">Treino de hoje: Ritmo — 10 km progressivo</p>
        </div>

        <div className="card p-10 text-center space-y-8">
          <div>
            <p className="text-lg font-semibold">Pronto pra correr?</p>
            <p className="text-sm text-text-secondary mt-1">10 km · Pace alvo 5:00/km · FC 155–165 bpm</p>
          </div>
          <button
            onClick={toggleRun}
            className="mx-auto w-28 h-28 rounded-full bg-brand text-brand-ink grid place-items-center
                       shadow-[0_16px_48px_-12px_var(--brand)] hover:scale-105 active:scale-95 transition-transform"
          >
            <Play size={44} className="translate-x-1" />
          </button>
          <p className="text-xs text-text-muted">O coach vai te acompanhar por voz durante o treino.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      {/* HUD */}
      <div className="card bg-gradient-to-b from-brand/5 to-transparent border-brand/10 p-6 md:p-8">
        <div className="grid grid-cols-3 gap-4 md:gap-8 text-center mb-6">
          <div>
            <p className="text-[10px] font-medium text-text-secondary uppercase tracking-widest">Pace</p>
            <p className="text-3xl md:text-5xl font-black text-brand tabular-nums mt-1">{pace}</p>
          </div>
          <div>
            <p className="text-[10px] font-medium text-text-secondary uppercase tracking-widest">Distância</p>
            <p className="text-3xl md:text-5xl font-black text-text-primary tabular-nums mt-1">
              {distance} <span className="text-lg font-medium">km</span>
            </p>
          </div>
          <div>
            <p className="text-[10px] font-medium text-text-secondary uppercase tracking-widest">Tempo</p>
            <p className="text-3xl md:text-5xl font-black text-text-primary tabular-nums mt-1">{formatTime(elapsed)}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-surface-300/50 rounded-2xl p-3 text-center">
            <p className="text-[10px] text-text-secondary uppercase tracking-wider">FC</p>
            <p className="text-xl md:text-2xl font-bold text-accent-red tabular-nums">{hr} <span className="text-xs font-medium">bpm</span></p>
          </div>
          <div className="bg-surface-300/50 rounded-2xl p-3 text-center">
            <p className="text-[10px] text-text-secondary uppercase tracking-wider">Cadência</p>
            <p className="text-xl md:text-2xl font-bold text-accent-green tabular-nums">{cadence} <span className="text-xs font-medium">spm</span></p>
          </div>
          <div className="bg-surface-300/50 rounded-2xl p-3 text-center">
            <p className="text-[10px] text-text-secondary uppercase tracking-wider">Elevação</p>
            <p className="text-xl md:text-2xl font-bold tabular-nums">{Math.round(elapsed * 0.3)} <span className="text-xs font-medium">m</span></p>
          </div>
          <div className="bg-surface-300/50 rounded-2xl p-3 text-center">
            <p className="text-[10px] text-text-secondary uppercase tracking-wider">Zona FC</p>
            <p className="text-xl md:text-2xl font-bold text-brand tabular-nums">Z{hr > 165 ? '3' : hr > 155 ? '2' : '1'}</p>
          </div>
        </div>

        {/* Barra de FC */}
        <div className="mt-4 h-2 bg-surface-300 rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-accent-green via-accent-yellow to-accent-red rounded-full transition-all duration-1000"
            style={{ width: `${Math.min(100, ((hr - 100) / 80) * 100)}%` }} />
        </div>
        <div className="flex justify-between text-[10px] text-text-secondary mt-1">
          <span>100</span><span>Z2</span><span>Z3</span><span>180</span>
        </div>
      </div>

      {/* Cue de voz */}
      {showCue && currentCue && (
        <div className="animate-slide-up flex items-center gap-3 p-4 rounded-2xl border border-brand/25 bg-brand/[0.06]">
          <div className="relative grid place-items-center w-10 h-10 rounded-full bg-brand/15 text-brand shrink-0">
            <Volume2 size={18} />
            <span className="absolute inset-0 rounded-full border border-brand/40 animate-pulse-ring" />
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-[11px] font-semibold text-brand uppercase tracking-wider">Coach ao vivo</span>
            <p className="text-sm md:text-base font-medium">{currentCue}</p>
          </div>
        </div>
      )}

      {/* Controles */}
      <div className="flex items-center justify-center gap-6">
        <button
          onClick={toggleRun}
          className={`w-16 h-16 rounded-full flex items-center justify-center text-white transition-all duration-200 shadow-lg
            ${status === 'running' ? 'bg-accent-orange shadow-accent-orange/20' : 'bg-accent-green shadow-accent-green/20'}`}
        >
          {status === 'running' ? <Pause size={28} /> : <Play size={28} />}
        </button>
        <button onClick={stopRun} className="w-12 h-12 rounded-full bg-accent-red/20 text-accent-red hover:bg-accent-red/30 flex items-center justify-center transition-all">
          <StopCircle size={20} />
        </button>
        <button className="w-12 h-12 rounded-xl bg-surface-200 text-text-secondary hover:text-text-primary hover:bg-surface-300 flex items-center justify-center transition-all border border-border-light">
          <Map size={20} />
        </button>
      </div>
    </div>
  )
}
