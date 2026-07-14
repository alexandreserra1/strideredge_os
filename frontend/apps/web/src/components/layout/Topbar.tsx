import { Moon, Sun, Bell, LogOut } from 'lucide-react'
import { useTheme } from './ThemeProvider'

interface TopbarProps {
  onNotifications?: () => void
  onLogout?: () => void
}

export default function Topbar({ onNotifications, onLogout }: TopbarProps) {
  const { theme, setTheme } = useTheme()

  return (
    <header className="h-16 glass border-b border-border-light flex items-center justify-between px-4 md:px-6 sticky top-0 z-40">
      <div className="md:hidden">
        <span className="text-lg font-bold">Strider<span className="text-brand">Edge</span></span>
      </div>

      <div className="flex items-center gap-2 ml-auto">
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
