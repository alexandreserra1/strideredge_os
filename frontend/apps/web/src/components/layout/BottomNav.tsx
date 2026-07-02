import {
  LayoutDashboard, CalendarDays, Activity, Play, Dumbbell,
} from 'lucide-react'

interface BottomNavProps {
  currentRoute: string
  onNavigate: (route: string) => void
}

const items = [
  { id: 'dashboard', icon: LayoutDashboard, label: 'Início' },
  { id: 'plano', icon: CalendarDays, label: 'Plano' },
  { id: 'detalhe', icon: Activity, label: 'Treinos' },
  { id: 'corrida', icon: Play, label: 'Correr' },
  { id: 'hyrox', icon: Dumbbell, label: 'HYROX' },
]

export default function BottomNav({ currentRoute, onNavigate }: BottomNavProps) {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-surface-100/95 backdrop-blur-xl border-t border-border-light z-50 safe-area-bottom">
      <div className="flex justify-around items-center h-16 px-2">
        {items.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-all duration-200 min-w-0
              ${currentRoute === id
                ? 'text-lime'
                : 'text-text-secondary hover:text-text-primary'
              }`}
          >
            <Icon size={20} />
            <span className="text-[10px] font-medium leading-tight">{label}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}
