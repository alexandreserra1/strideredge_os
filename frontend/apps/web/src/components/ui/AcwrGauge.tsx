interface AcwrGaugeProps {
  value: number
  status: string
}

const statusConfig: Record<string, { color: string; bg: string; label: string }> = {
  low: { color: 'text-accent-yellow', bg: 'bg-accent-yellow/20', label: 'Atenção' },
  optimal: { color: 'text-accent-green', bg: 'bg-accent-green/20', label: 'Pronto' },
  high: { color: 'text-accent-orange', bg: 'bg-accent-orange/20', label: 'Limiar' },
  very_high: { color: 'text-accent-red', bg: 'bg-accent-red/20', label: 'Alerta' },
}

export default function AcwrGauge({ value, status }: AcwrGaugeProps) {
  const cfg = statusConfig[status] || statusConfig.optimal
  const pct = Math.min(value / 1.5, 1) * 100

  return (
    <div className="kpi-card">
      <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">Prontidão · ACWR</span>
      <div className="flex items-center justify-between mt-2">
        <div className="relative w-16 h-16">
          <svg viewBox="0 0 36 36" className="w-16 h-16 -rotate-90">
            <path d="M18 2 a16 16 0 1 1 0 32 a16 16 0 1 1 0 -32"
              stroke="#1F2B00" strokeWidth="4" fill="none" />
            <path d="M18 2 a16 16 0 1 1 0 32 a16 16 0 1 1 0 -32"
              stroke="currentColor" strokeWidth="4" fill="none"
              strokeDasharray={`${pct} ${100 - pct}`}
              strokeLinecap="round" className={cfg.color} />
          </svg>
          <span className={`absolute inset-0 flex items-center justify-center text-lg font-bold ${cfg.color}`}>
            {value.toFixed(2)}
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className={`text-sm font-semibold ${cfg.color}`}>{cfg.label}</span>
          <span className="text-xs text-text-secondary">Carga ideal: 0.8–1.3</span>
        </div>
      </div>
      <div className="mt-3 h-1.5 bg-surface-300 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${cfg.bg}`}
          style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
