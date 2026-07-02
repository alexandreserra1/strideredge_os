import { useState, useCallback } from 'react'
import { ThemeProvider } from './components/layout/ThemeProvider'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Landing from './pages/Landing'
import WorkoutDetail from './pages/WorkoutDetail'
import PlanScreen from './pages/PlanScreen'
import RunMode from './pages/RunMode'
import HyroxScreen from './pages/HyroxScreen'
import { mockAcwrCurrent } from './pages/mockData'

type Route = 'landing' | 'dashboard' | 'plano' | 'detalhe' | 'corrida' | 'hyrox'

export default function App() {
  const [route, setRoute] = useState<Route>('dashboard')
  const [acwr] = useState(mockAcwrCurrent.acwr)

  const navigate = useCallback((r: string) => {
    if (['landing', 'dashboard', 'plano', 'detalhe', 'corrida', 'hyrox'].includes(r)) {
      setRoute(r as Route)
    }
  }, [])

  const renderPage = () => {
    switch (route) {
      case 'landing':
        return <Landing onNavigate={navigate} />
      case 'dashboard':
        return <Dashboard onNavigate={navigate} />
      case 'plano':
        return <PlanScreen />
      case 'detalhe':
        return <WorkoutDetail onNavigate={navigate} />
      case 'corrida':
        return <RunMode />
      case 'hyrox':
        return <HyroxScreen />
      default:
        return <Dashboard onNavigate={navigate} />
    }
  }

  const isLanding = route === 'landing'

  return (
    <ThemeProvider>
      {isLanding ? (
        <div className="min-h-screen bg-surface">
          <header className="sticky top-0 z-50 bg-surface-100/80 backdrop-blur-xl border-b border-border-light">
            <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
              <button onClick={() => navigate('landing')} className="flex items-center gap-2">
                <span className="grid place-items-center w-7 h-7 rounded-lg bg-brand text-brand-ink font-black text-sm">S</span>
                <span className="font-bold tracking-tight">
                  Strider<span className="text-brand">Edge</span>
                </span>
              </button>
              <div className="flex items-center gap-3">
                <button onClick={() => navigate('dashboard')} className="btn-ghost text-sm">
                  Login
                </button>
                <button onClick={() => navigate('dashboard')} className="btn-primary text-sm">
                  Começar
                </button>
              </div>
            </div>
          </header>
          <Landing onNavigate={navigate} />
        </div>
      ) : (
        <Layout currentRoute={route} onNavigate={navigate} acwr={acwr}>
          {renderPage()}
        </Layout>
      )}
    </ThemeProvider>
  )
}
