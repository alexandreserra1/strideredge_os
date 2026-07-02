import {
  LayoutDashboard, CalendarDays, Activity, HeartPulse, Play, Dumbbell,
} from 'lucide-react'

interface BottomNavProps {
  currentRoute: string
  onNavigate: (route: string) => void
}

const items = [
  { id: 'dashboard', icon: LayoutDashboard, label: 'Início' },
  { id: 'plano', icon: CalendarDays, label: 'Plano' },
  { id: 'analise', icon: HeartPulse, label: 'Saúde' },
  { id: 'corrida', icon: Play, label: 'Correr' },
  { id: 'hyrox', icon: Dumbbell, label: 'HYROX' },
]

export default function BottomNav({ currentRoute, onNavigate }: BottomNavProps) {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 glass border-t border-border-light z-50">
      <div className="flex justify-around items-center h-16 px-2">
        {items.map(({ id, icon: Icon, label }) => {
          const active = currentRoute === id
          return (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className={`flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-all duration-200 min-w-0
                ${active ? 'text-brand bg-brand/10' : 'text-text-secondary hover:text-text-primary active:scale-95'}`}
            >
              <Icon size={20} strokeWidth={active ? 2.4 : 2} />
              <span className="text-[10px] font-medium leading-tight">{label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
