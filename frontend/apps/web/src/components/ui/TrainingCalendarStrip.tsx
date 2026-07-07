import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

export type TrainingDayStatus = 'done' | 'skipped' | 'none'
export interface TrainingDayInfo { status: TrainingDayStatus; activityId?: string }

// Domingo = índice 0
const WEEKDAY_LABELS = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']
const MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

function localISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

interface Props {
  /** status/atividade por dia (ISO yyyy-mm-dd) — cobre o histórico todo */
  days: Record<string, TrainingDayInfo>
  /** dia selecionado (a página mostra a análise dele inline) */
  selected?: string | null
  /** clicar num dia (passado/hoje) seleciona — análise acontece NA página, não navega */
  onSelectDay?: (iso: string) => void
}

/** Célula de dia: número dentro de um chip colorido pelo status; hoje = anel; selecionado = brand. */
function DayCell({ d, info, isToday, isFuture, selected, onSelect, compact = false }: {
  d: Date; info: TrainingDayInfo; isToday: boolean; isFuture: boolean
  selected: boolean; onSelect?: (iso: string) => void; compact?: boolean
}) {
  const iso = localISO(d)
  const status = info.status
  const label = status === 'done' ? 'treino feito' : status === 'skipped' ? 'treino pulado' : 'sem treino'
  const palette = status === 'done'
    ? 'bg-accent-green/15 text-accent-green border-accent-green/30'
    : status === 'skipped'
    ? 'bg-accent-red/10 text-accent-red border-accent-red/25'
    : 'bg-transparent text-text-muted border-border-light'
  return (
    <button
      aria-label={`Dia ${iso} — ${label}`}
      disabled={isFuture || !onSelect}
      onClick={() => onSelect?.(iso)}
      className={`flex flex-col items-center justify-center rounded-xl border transition-all duration-200
        ${compact ? 'w-9 h-11' : 'w-11 h-14 shrink-0'}
        ${palette}
        ${isFuture ? 'opacity-30 cursor-default' : 'hover:scale-105 hover:border-brand/40 cursor-pointer'}
        ${selected ? 'ring-2 ring-brand scale-105' : ''}`}
      style={isToday && !selected ? { boxShadow: '0 0 0 1.5px var(--brand)' } : undefined}
    >
      {!compact && <span className="text-[9px] uppercase opacity-70">{WEEKDAY_LABELS[d.getDay()]}</span>}
      <span className={`tabular-nums font-semibold ${compact ? 'text-[12px]' : 'text-sm'}`}>{d.getDate()}</span>
      <span className="w-1 h-1 rounded-full"
        style={{ background: status === 'done' ? '#34D399' : status === 'skipped' ? '#F87171' : 'transparent' }} />
    </button>
  )
}

export default function TrainingCalendarStrip({ days, selected, onSelectDay }: Props) {
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
      <div className="flex items-center justify-between mb-4">
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
        <div className="flex gap-2 overflow-x-auto scrollbar-hide sm:justify-between pb-1">
          {stripDays.map(d => {
            const iso = localISO(d)
            return (
              <DayCell key={iso} d={d} info={info(iso)} isToday={iso === todayISO}
                isFuture={false} selected={iso === selected} onSelect={onSelectDay} />
            )
          })}
        </div>
      ) : (
        <div className="grid grid-cols-7 gap-1.5 animate-fade-in justify-items-center">
          {WEEKDAY_LABELS.map((l, i) => (
            <span key={i} className="text-[10px] text-text-secondary">{l}</span>
          ))}
          {cells.map((d, i) => {
            if (!d) return <span key={`pad-${i}`} />
            const iso = localISO(d)
            return (
              <DayCell key={iso} d={d} info={info(iso)} isToday={iso === todayISO} compact
                isFuture={d > now} selected={iso === selected} onSelect={onSelectDay} />
            )
          })}
        </div>
      )}

      <div className="flex items-center justify-end gap-3 mt-3">
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
