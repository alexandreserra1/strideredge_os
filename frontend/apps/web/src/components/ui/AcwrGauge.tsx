import { Info } from 'lucide-react'
import AnimatedNumber from './AnimatedNumber'

const ACWR_HINT =
  'Prontidão (ACWR): razão entre a carga aguda (últimos 7 dias) e a crônica (últimos 28 dias). ' +
  'Entre 0.8 e 1.3 = zona ideal (pode treinar forte). Acima de ~1.5 = pico de risco de lesão.'

interface AcwrGaugeProps {
  value: number
  status: string
}

const statusConfig: Record<string, { color: string; hex: string; label: string }> = {
  low: { color: 'text-accent-yellow', hex: '#F5B14C', label: 'Atenção' },
  optimal: { color: 'text-accent-green', hex: '#34D399', label: 'Pronto' },
  high: { color: 'text-accent-orange', hex: '#FF8A4C', label: 'Limiar' },
  very_high: { color: 'text-accent-red', hex: '#FB5E7E', label: 'Alerta' },
}

export default function AcwrGauge({ value, status }: AcwrGaugeProps) {
  const cfg = statusConfig[status] || statusConfig.optimal
  const pct = Math.min(value / 1.5, 1) * 100

  return (
    <div className="kpi-card">
      <span className="flex items-center gap-1.5 text-xs font-medium text-text-secondary uppercase tracking-wider">
        Prontidão · ACWR
        <span title={ACWR_HINT} className="cursor-help text-text-muted hover:text-text-secondary transition-colors">
          <Info size={12} />
        </span>
      </span>
      <div className="flex items-center justify-between mt-2">
        <div className="relative w-16 h-16">
          <svg viewBox="0 0 36 36" className="w-16 h-16 -rotate-90">
            <path d="M18 2 a16 16 0 1 1 0 32 a16 16 0 1 1 0 -32"
              stroke="var(--surface-300)" strokeWidth="4" fill="none" />
            <path d="M18 2 a16 16 0 1 1 0 32 a16 16 0 1 1 0 -32"
              stroke={cfg.hex} strokeWidth="4" fill="none"
              strokeDasharray={`${pct} ${100 - pct}`}
              strokeLinecap="round"
              style={{ transition: 'stroke-dasharray .7s cubic-bezier(.22,1,.36,1)' }} />
          </svg>
          <AnimatedNumber value={value} decimals={2}
            className={`absolute inset-0 flex items-center justify-center text-lg font-bold tabular-nums ${cfg.color}`} />
        </div>
        <div className="flex flex-col items-end">
          <span className={`text-sm font-semibold ${cfg.color}`}>{cfg.label}</span>
          <span className="text-xs text-text-secondary">Carga ideal: 0.8–1.3</span>
        </div>
      </div>
      <div className="mt-3 h-1.5 bg-surface-300 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: cfg.hex }} />
      </div>
    </div>
  )
}
