export type TrainingDayStatus = 'done' | 'skipped' | 'none'

export interface TrainingCalendarEntry {
  /** ISO yyyy-mm-dd */
  date: string
  status: TrainingDayStatus
}

// Domingo = índice 0
const WEEKDAY_LABELS = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']

const STATUS_META: Record<TrainingDayStatus, { title: string; color: string }> = {
  done:    { title: 'Feito',      color: '#34D399' },
  skipped: { title: 'Pulado',     color: '#F87171' },
  none:    { title: 'Sem treino', color: 'transparent' },
}

function localISO(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

export default function TrainingCalendarStrip({ entries }: { entries: TrainingCalendarEntry[] }) {
  const todayISO = localISO(new Date())

  return (
    <div>
      <div className="flex gap-1.5 overflow-x-auto scrollbar-hide sm:justify-between">
        {entries.map(({ date, status }) => {
          const d = new Date(date + 'T00:00:00')
          const isToday = date === todayISO
          const meta = STATUS_META[status]
          return (
            <div key={date} className="flex flex-col items-center gap-1 shrink-0 min-w-[28px] sm:flex-1">
              <span className="text-[10px] text-text-secondary">{WEEKDAY_LABELS[d.getDay()]}</span>
              <span
                className={`text-[12px] tabular-nums ${isToday ? 'font-bold text-text-primary' : 'text-text-muted'}`}
              >
                {d.getDate()}
              </span>
              <span
                title={meta.title}
                className="w-3.5 h-3.5 rounded-md"
                style={{
                  background: meta.color,
                  border: status === 'none' ? '1px solid var(--border-medium)' : 'none',
                  boxShadow: isToday ? '0 0 0 1.5px var(--brand)' : undefined,
                }}
              />
            </div>
          )
        })}
      </div>

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
      <span
        className="w-2 h-2 rounded-[3px]"
        style={color ? { background: color } : { border: '1px solid var(--border-medium)' }}
      />
      {label}
    </span>
  )
}
