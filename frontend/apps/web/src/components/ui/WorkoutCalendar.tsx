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
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold capitalize">{MONTHS[month.getMonth()]} {month.getFullYear()}</h2>
          <p className="text-xs text-text-secondary mt-0.5">{monthDone} treino{monthDone === 1 ? '' : 's'} no mês</p>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
            aria-label="Mês anterior"
            className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-300 transition-colors">
            <ChevronLeft size={18} />
          </button>
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
            aria-label="Próximo mês" disabled={atCurrent}
            className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-300 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1.5">
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
          const color = done ? (TYPE_COLOR[day!.type ?? 'run'] ?? TYPE_COLOR.run) : undefined
          return (
            <button
              key={key}
              disabled={!done || !onOpenWorkout}
              onClick={() => done && onOpenWorkout?.(day!.activityId!)}
              aria-label={`Dia ${d.getDate()}${done ? ' — treino feito' : missed ? ' — sem treino' : ''}`}
              className={`aspect-square rounded-xl border flex flex-col items-center justify-center gap-1 transition-all duration-200
                ${done ? 'cursor-pointer hover:scale-[1.06]' : 'cursor-default'}
                ${future ? 'opacity-35 border-transparent' : ''}`}
              style={{
                background: done ? `${color}1f` : missed ? 'rgba(248,113,113,0.06)' : 'transparent',
                borderColor: done ? `${color}55` : missed ? 'rgba(248,113,113,0.20)' : 'var(--border-light)',
                boxShadow: key === todayISO ? '0 0 0 1.5px var(--brand)' : undefined,
              }}
            >
              <span className={`text-sm tabular-nums ${done ? 'font-semibold text-text-primary' : 'text-text-secondary'}`}>
                {d.getDate()}
              </span>
              <span className="h-1.5 w-1.5 rounded-full"
                style={{ background: done ? color : missed ? 'rgba(248,113,113,0.5)' : 'transparent' }} />
            </button>
          )
        })}
      </div>

      <div className="flex items-center justify-end gap-3 mt-4">
        <Legend label="Treino" color="#34D399" />
        <Legend label="Sem treino" color="rgba(248,113,113,0.6)" />
        <Legend label="Hoje" ring />
      </div>
    </div>
  )
}

function Legend({ label, color, ring }: { label: string; color?: string; ring?: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-[10px] text-text-muted">
      <span className="w-2.5 h-2.5 rounded-[4px]"
        style={ring ? { boxShadow: '0 0 0 1.5px var(--brand)' } : { background: color }} />
      {label}
    </span>
  )
}
