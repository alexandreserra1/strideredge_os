import { Moon, Sun, Bell, LogOut } from 'lucide-react'
import { useTheme } from './ThemeProvider'

interface TopbarProps {
  acwr?: number
  onNotifications?: () => void
  onLogout?: () => void
}

// Cor da prontidão a partir do ACWR (sweet spot 0.8–1.3)
function readiness(acwr?: number) {
  if (acwr == null) return { color: 'var(--text-muted)', label: '—' }
  if (acwr < 0.8) return { color: '#38BDF8', label: 'Leve' }
  if (acwr <= 1.3) return { color: '#34D399', label: 'Ótima' }
  if (acwr <= 1.5) return { color: '#F5B14C', label: 'Atenção' }
  return { color: '#FB5E7E', label: 'Alta' }
}

export default function Topbar({ acwr, onNotifications, onLogout }: TopbarProps) {
  const { theme, setTheme } = useTheme()
  const r = readiness(acwr)

  return (
    <header className="h-16 glass border-b border-border-light flex items-center justify-between px-4 md:px-6 sticky top-0 z-40">
      <div className="md:hidden">
        <span className="text-lg font-bold">Strider<span className="text-brand">Edge</span></span>
      </div>

      <div className="flex items-center gap-2 ml-auto">
        {/* pílula de prontidão (substitui o mascote — informativa e sóbria) */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-200 border border-border-light">
          <span className="w-2 h-2 rounded-full" style={{ background: r.color, boxShadow: `0 0 8px ${r.color}` }} />
          <span className="text-xs font-medium text-text-secondary">
            Prontidão <span className="text-text-primary font-semibold tabular-nums">{acwr?.toFixed(2) ?? '—'}</span>
          </span>
        </div>

        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="p-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-surface-200 transition-all duration-200"
          title={theme === 'dark' ? 'Modo claro' : 'Modo escuro'}
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <button
          onClick={onNotifications}
          className="p-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-surface-200 transition-all duration-200 relative"
        >
          <Bell size={18} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-brand rounded-full" />
        </button>

        {onLogout && (
          <button
            onClick={onLogout}
            title="Sair"
            className="p-2 rounded-xl text-text-secondary hover:text-accent-red hover:bg-surface-200 transition-all duration-200"
          >
            <LogOut size={18} />
          </button>
        )}
      </div>
    </header>
  )
}
