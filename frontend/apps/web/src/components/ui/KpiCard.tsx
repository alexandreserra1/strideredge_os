import type { ReactNode } from 'react'

interface KpiCardProps {
  label: string
  value: string | number
  sub?: string
  icon?: ReactNode
  accent?: 'lime' | 'green' | 'yellow' | 'red' | 'orange' | 'blue'
  trend?: 'up' | 'down' | 'stable'
  children?: ReactNode
}

const accentColors = {
  lime: 'text-lime border-lime/30',
  green: 'text-accent-green border-accent-green/30',
  yellow: 'text-accent-yellow border-accent-yellow/30',
  red: 'text-accent-red border-accent-red/30',
  orange: 'text-accent-orange border-accent-orange/30',
  blue: 'text-accent-blue border-accent-blue/30',
}

const trendIcons = {
  up: '↑',
  down: '↓',
  stable: '→',
}

export default function KpiCard({ label, value, sub, icon, accent = 'lime', trend, children }: KpiCardProps) {
  return (
    <div className={`kpi-card relative overflow-hidden ${children ? 'pb-0' : ''}`}>
      <div className="flex items-start justify-between mb-1">
        <span className="text-xs font-medium text-text-secondary uppercase tracking-wider">{label}</span>
        {icon && <span className={`${accentColors[accent].split(' ')[0]} opacity-70`}>{icon}</span>}
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
