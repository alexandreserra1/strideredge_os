import { Moon, Sun } from 'lucide-react'
import { useTheme } from './ThemeProvider'

/** Botão sol/lua reutilizável (topbar do app, landing pública e login). */
export default function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  return (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      title={theme === 'dark' ? 'Modo claro' : 'Modo escuro'}
      className="p-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-surface-200 transition-all duration-200"
    >
      {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  )
}
