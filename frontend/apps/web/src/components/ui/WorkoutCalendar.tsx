import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

export interface CalendarDay { activityId?: string; type?: string }

const WEEKDAYS = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']
const MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

// cor do ponto por modalidade (o dia feito herda um tom da atividade)
const TYPE_COLOR: Record<string, string> = {
  run: '#34D399', treadmill: '#38BDF8', hyrox: '#FF8A4C',
  crossfit: '#FBBF24', strength: '#FB5E7E', recovery: '#6B7079',
}

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Calendário mensal (estilo Strava/Apple): dia feito = clicável e colorido pelo tipo,
 * dia passado sem treino = vermelho suave, futuro/hoje-sem = neutro. Clicar abre o treino. */
export default function WorkoutCalendar({ days, onOpenWorkout }: {
  days: Record<string, CalendarDay>
  onOpenWorkout?: (activityId: string) => void
}) {
  const now = new Date(); now.setHours(0, 0, 0, 0)
  const todayISO = iso(now)
  const [month, setMonth] = useState(() => new Date(now.getFullYear(), now.getMonth(), 1))
  const atCurrent = month.getFullYear() === now.getFullYear() && month.getMonth() === now.getMonth()

  const firstWeekday = month.getDay()
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  const cells: (Date | null)[] = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1)),
  ]

  const monthDone = cells.filter(d => d && days[iso(d)]?.activityId).length

  return (
    <div className="card max-w-sm">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-base font-semibold capitalize">{MONTHS[month.getMonth()]} {month.getFullYear()}</h2>
          <p className="text-[11px] text-text-secondary mt-0.5">{monthDone} treino{monthDone === 1 ? '' : 's'} no mês</p>
        </div>
        <div className="flex items-center gap-0.5">
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
            aria-label="Mês anterior"
            className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-300 transition-colors">
            <ChevronLeft size={16} />
          </button>
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
            aria-label="Próximo mês" disabled={atCurrent}
            className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-300 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-0.5">
        {WEEKDAYS.map((l, i) => (
          <span key={i} className="text-[10px] text-text-muted text-center pb-1">{l}</span>
        ))}
        {cells.map((d, i) => {
          if (!d) return <span key={`p${i}`} />
          const key = iso(d)
          const day = days[key]
          const done = !!day?.activityId
          const future = d > now
          const missed = !done && !future && key !== todayISO
          const isToday = key === todayISO
          // UMA semântica de cor: feito=verde da marca · não treinado=vermelho suave · futuro=neutro.
          // A modalidade é só um pontinho discreto embaixo (não pinta o dia inteiro).
          return (
            <button
              key={key}
              disabled={!done || !onOpenWorkout}
              onClick={() => done && onOpenWorkout?.(day!.activityId!)}
              aria-label={`Dia ${d.getDate()}${done ? ' — treino feito' : missed ? ' — sem treino' : ''}`}
              className={`relative aspect-square rounded-lg flex items-center justify-center text-[12px] tabular-nums transition-colors duration-150
                ${done
                  ? 'cursor-pointer font-semibold text-accent-green bg-accent-green/10 hover:bg-accent-green/20'
                  : missed
                  ? 'text-accent-red/60 bg-accent-red/[0.04]'
                  : future ? 'text-text-muted/40' : 'text-text-secondary'}
                ${isToday ? 'ring-1 ring-brand ring-inset font-semibold' : ''}`}
            >
              {d.getDate()}
              {done && (
                <span className="absolute bottom-1 h-1 w-1 rounded-full"
                  style={{ background: TYPE_COLOR[day!.type ?? 'run'] ?? TYPE_COLOR.run }} />
              )}
            </button>
          )
        })}
      </div>

      <div className="flex items-center justify-between gap-3 mt-3">
        <Legend label="Feito" swatch="bg-accent-green/30" />
        <Legend label="Sem treino" swatch="bg-accent-red/20" />
        <Legend label="Hoje" ring />
      </div>
    </div>
  )
}

function Legend({ label, swatch, ring }: { label: string; swatch?: string; ring?: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-[10px] text-text-muted">
      <span className={`w-2.5 h-2.5 rounded-[4px] ${swatch ?? ''}`}
        style={ring ? { boxShadow: 'inset 0 0 0 1.5px var(--brand)' } : undefined} />
      {label}
    </span>
  )
}
