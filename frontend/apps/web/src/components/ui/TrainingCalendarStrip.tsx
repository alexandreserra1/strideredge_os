import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

export type TrainingDayStatus = 'done' | 'skipped' | 'none'
export interface TrainingDayInfo { status: TrainingDayStatus; activityId?: string }

// Domingo = índice 0
const WEEKDAY_LABELS = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']
const MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

const STATUS_META: Record<TrainingDayStatus, { title: string; color: string }> = {
  done:    { title: 'Treino feito — clique para abrir', color: '#34D399' },
  skipped: { title: 'Pulado', color: '#F87171' },
  none:    { title: 'Sem treino', color: 'transparent' },
}

function localISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

interface Props {
  /** status/atividade por dia (ISO yyyy-mm-dd) — cobre o histórico todo */
  days: Record<string, TrainingDayInfo>
  /** clique num dia com treino abre a atividade */
  onSelect?: (activityId: string) => void
}

/** Quadradinho de status de um dia (compartilhado pelos dois modos). Clicável quando há treino. */
function DaySquare({ iso, info, isToday, onSelect, size = 'w-3.5 h-3.5' }: {
  iso: string; info: TrainingDayInfo; isToday: boolean
  onSelect?: (id: string) => void; size?: string
}) {
  const meta = STATUS_META[info.status]
  const clickable = !!(info.activityId && onSelect)
  const style = {
    background: meta.color,
    border: info.status === 'none' ? '1px solid var(--border-medium)' : 'none',
    boxShadow: isToday ? '0 0 0 1.5px var(--brand)' : undefined,
  }
  if (!clickable) return <span title={meta.title} className={`${size} rounded-md block`} style={style} />
  return (
    <button
      title={meta.title}
      aria-label={`Abrir treino de ${iso}`}
      onClick={() => onSelect!(info.activityId!)}
      className={`${size} rounded-md block transition-transform hover:scale-125 hover:ring-2 hover:ring-[var(--brand)] cursor-pointer`}
      style={style}
    />
  )
}

export default function TrainingCalendarStrip({ days, onSelect }: Props) {
  const [view, setView] = useState<'strip' | 'month'>('strip')
  const now = new Date(); now.setHours(0, 0, 0, 0)
  const todayISO = localISO(now)
  const [month, setMonth] = useState(() => new Date(now.getFullYear(), now.getMonth(), 1))

  const info = (iso: string): TrainingDayInfo => days[iso] ?? { status: 'none' }
  const atCurrentMonth = month.getFullYear() === now.getFullYear() && month.getMonth() === now.getMonth()

  // ---- modo strip: últimos 14 dias ----
  const stripDays = Array.from({ length: 14 }, (_, i) => {
    const d = new Date(now); d.setDate(now.getDate() - (13 - i))
    return d
  })

  // ---- modo mês: grade 7 colunas do mês selecionado ----
  const firstWeekday = month.getDay()
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  const cells: (Date | null)[] = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1)),
  ]

  return (
    <div>
      {/* header: título/navegação + toggle de visão */}
      <div className="flex items-center justify-between mb-3">
        {view === 'strip' ? (
          <p className="text-xs text-text-secondary uppercase tracking-wider">Últimas 2 semanas</p>
        ) : (
          <div className="flex items-center gap-1">
            <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
              aria-label="Mês anterior"
              className="p-1 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-300 transition-colors">
              <ChevronLeft size={16} />
            </button>
            <span className="text-xs font-semibold min-w-[130px] text-center capitalize">
              {MONTHS[month.getMonth()]} {month.getFullYear()}
            </span>
            <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
              aria-label="Próximo mês"
              disabled={atCurrentMonth}
              className="p-1 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-300 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
              <ChevronRight size={16} />
            </button>
          </div>
        )}
        <div className="flex items-center bg-surface-300 rounded-lg p-0.5">
          {(['strip', 'month'] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all
                ${view === v ? 'bg-surface-100 text-text-primary' : 'text-text-secondary hover:text-text-primary'}`}>
              {v === 'strip' ? '2 semanas' : 'Mês'}
            </button>
          ))}
        </div>
      </div>

      {view === 'strip' ? (
        <div className="flex gap-1.5 overflow-x-auto scrollbar-hide sm:justify-between">
          {stripDays.map(d => {
            const iso = localISO(d)
            return (
              <div key={iso} className="flex flex-col items-center gap-1 shrink-0 min-w-[28px] sm:flex-1">
                <span className="text-[10px] text-text-secondary">{WEEKDAY_LABELS[d.getDay()]}</span>
                <span className={`text-[12px] tabular-nums ${iso === todayISO ? 'font-bold text-text-primary' : 'text-text-muted'}`}>
                  {d.getDate()}
                </span>
                <DaySquare iso={iso} info={info(iso)} isToday={iso === todayISO} onSelect={onSelect} />
              </div>
            )
          })}
        </div>
      ) : (
        <div className="grid grid-cols-7 gap-y-2 animate-fade-in">
          {WEEKDAY_LABELS.map((l, i) => (
            <span key={i} className="text-[10px] text-text-secondary text-center">{l}</span>
          ))}
          {cells.map((d, i) => {
            if (!d) return <span key={`pad-${i}`} />
            const iso = localISO(d)
            const future = d > now
            return (
              <div key={iso} className={`flex flex-col items-center gap-1 ${future ? 'opacity-35' : ''}`}>
                <span className={`text-[11px] tabular-nums ${iso === todayISO ? 'font-bold text-text-primary' : 'text-text-muted'}`}>
                  {d.getDate()}
                </span>
                <DaySquare iso={iso} info={info(iso)} isToday={iso === todayISO} onSelect={onSelect} size="w-4 h-4" />
              </div>
            )
          })}
        </div>
      )}

      <div className="flex items-center justify-end gap-3 mt-2.5">
        <LegendItem label="Feito" color="#34D399" />
        <LegendItem label="Pulado" color="#F87171" />
        <LegendItem label="Sem treino" />
      </div>
    </div>
  )
}

function LegendItem({ label, color }: { label: string; color?: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[10px] text-text-muted">
      <span className="w-2 h-2 rounded-[3px]"
        style={color ? { background: color } : { border: '1px solid var(--border-medium)' }} />
      {label}
    </span>
  )
}
