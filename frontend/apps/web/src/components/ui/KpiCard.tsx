import type { ReactNode } from 'react'
import { Info } from 'lucide-react'

interface KpiCardProps {
  label: string
  value: string | number
  sub?: string
  hint?: string
  icon?: ReactNode
  accent?: 'lime' | 'green' | 'yellow' | 'red' | 'orange' | 'blue'
  trend?: 'up' | 'down' | 'stable'
  children?: ReactNode
}

const accentColors = {
  lime: 'text-lime',
  green: 'text-accent-green',
  yellow: 'text-accent-yellow',
  red: 'text-accent-red',
  orange: 'text-accent-orange',
  blue: 'text-accent-blue',
}

const trendIcons = { up: '↑', down: '↓', stable: '→' }

export default function KpiCard({ label, value, sub, hint, icon, accent = 'lime', trend, children }: KpiCardProps) {
  return (
    <div className={`kpi-card relative overflow-hidden ${children ? 'pb-0' : ''}`}>
      <div className="flex items-start justify-between mb-1">
        <span className="flex items-center gap-1.5 text-xs font-medium text-text-secondary uppercase tracking-wider">
          {label}
          {hint && (
            <span title={hint} className="cursor-help text-text-muted hover:text-text-secondary transition-colors">
              <Info size={12} />
            </span>
          )}
        </span>
        {icon && <span className={`${accentColors[accent]} opacity-70`}>{icon}</span>}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl md:text-3xl font-bold tracking-tight text-text-primary">{value}</span>
        {trend && (
          <span className={`text-sm font-medium ${
            trend === 'up' ? 'text-accent-green' : trend === 'down' ? 'text-accent-red' : 'text-text-secondary'
          }`}>
            {trendIcons[trend]}
          </span>
        )}
      </div>
      {sub && <p className="text-xs text-text-secondary mt-0.5">{sub}</p>}
      {children}
    </div>
  )
}
