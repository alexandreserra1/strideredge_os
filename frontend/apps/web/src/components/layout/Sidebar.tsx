import { Clapperboard } from 'lucide-react'

interface SidebarProps {
  currentRoute: string
  onNavigate: (route: string) => void
}

const menu = [
  { id: 'video', label: 'Análise de Forma', icon: Clapperboard },
]

export default function Sidebar({ currentRoute, onNavigate }: SidebarProps) {
  return (
    <aside className="w-[220px] min-h-screen bg-surface-100 border-r border-border-light flex flex-col shrink-0 hide-mobile">
      <div className="p-5 border-b border-border-light">
        <button onClick={() => onNavigate('video')} className="flex items-center gap-2.5">
          <span className="grid place-items-center w-8 h-8 rounded-lg bg-brand text-brand-ink font-black text-sm">S</span>
          <span className="text-lg font-bold tracking-tight">
            Strider<span className="text-brand">Edge</span>
          </span>
        </button>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {menu.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200
              ${currentRoute === id
                ? 'bg-lime/10 text-lime border border-lime/20'
                : 'text-text-secondary hover:text-text-primary hover:bg-white/5 dark:hover:bg-white/5 border border-transparent'
              }`}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </nav>
    </aside>
  )
}
