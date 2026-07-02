import type { ReactNode } from 'react'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import BottomNav from './BottomNav'

interface LayoutProps {
  children: ReactNode
  currentRoute: string
  onNavigate: (route: string) => void
  acwr?: number
}

export default function Layout({ children, currentRoute, onNavigate, acwr }: LayoutProps) {
  return (
    <div className="flex min-h-screen bg-surface">
      <Sidebar currentRoute={currentRoute} onNavigate={onNavigate} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar acwr={acwr} />
        <main className="flex-1 p-4 md:p-6 lg:p-8 pb-20 md:pb-8">
          {children}
        </main>
      </div>
      <BottomNav currentRoute={currentRoute} onNavigate={onNavigate} />
    </div>
  )
}
