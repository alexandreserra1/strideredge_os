import { useState, useCallback } from 'react'
import { ThemeProvider } from './components/layout/ThemeProvider'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Landing from './pages/Landing'
import WorkoutDetail from './pages/WorkoutDetail'
import PlanScreen from './pages/PlanScreen'
import RunMode from './pages/RunMode'
import HyroxScreen from './pages/HyroxScreen'
import AnaliseSaude from './pages/AnaliseSaude'
import Login from './pages/Login'
import { session, useTrainingLoad, latestAcwr } from '@strideredge/core'
import { mockAcwrCurrent } from './pages/mockData'

type Route = 'landing' | 'login' | 'dashboard' | 'plano' | 'detalhe' | 'analise' | 'corrida' | 'hyrox'

export default function App() {
  // Sessão: token (conta) ou modo convidado (local). Sem sessão -> landing pública.
  const [authed, setAuthed] = useState(() => !!(session.get() || localStorage.getItem('se_guest')))
  const [route, setRoute] = useState<Route>(authed ? 'dashboard' : 'landing')
  // prontidão do Topbar: ACWR real do backend; mock só quando ele está off
  const { data: load } = useTrainingLoad()
  const acwr = (latestAcwr(load ?? []) ?? mockAcwrCurrent).acwr
  // treino a abrir no detalhe (deep-link do calendário/feed)
  const [detailId, setDetailId] = useState<string | null>(null)

  const navigate = useCallback((r: string) => {
    if (!['landing', 'login', 'dashboard', 'plano', 'detalhe', 'analise', 'corrida', 'hyrox'].includes(r)) return
    // visitante só circula entre landing e login; o app pede sessão
    if (!authed && r !== 'landing' && r !== 'login') { setRoute('login'); return }
    setRoute(r as Route)
  }, [authed])

  const onAuthed = useCallback((user: { name: string } | null) => {
    if (user === null) localStorage.setItem('se_guest', '1')   // modo local
    setAuthed(true)
    setRoute('dashboard')
  }, [])

  const onLogout = useCallback(() => {
    session.clear()
    localStorage.removeItem('se_guest')
    setAuthed(false)
    setRoute('landing')
  }, [])

  const openWorkout = useCallback((id: string) => {
    setDetailId(id)
    setRoute('detalhe')
  }, [])

  const renderPage = () => {
    switch (route) {
      case 'landing':
        return <Landing onNavigate={navigate} />
      case 'login':
        return <Login onAuthed={onAuthed} onBack={() => setRoute('landing')} />
      case 'dashboard':
        return <Dashboard onNavigate={navigate} onOpenWorkout={openWorkout} />
      case 'plano':
        return <PlanScreen />
      case 'detalhe':
        return <WorkoutDetail onNavigate={navigate} initialId={detailId} />
      case 'analise':
        return <AnaliseSaude onOpenWorkout={openWorkout} />
      case 'corrida':
        return <RunMode />
      case 'hyrox':
        return <HyroxScreen />
      default:
        return <Dashboard onNavigate={navigate} onOpenWorkout={openWorkout} />
    }
  }

  const isLanding = route === 'landing'
  if (route === 'login') return <ThemeProvider><Login onAuthed={onAuthed} onBack={() => setRoute('landing')} /></ThemeProvider>

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
                <button onClick={() => navigate('login')} className="btn-ghost text-sm">
                  Login
                </button>
                <button onClick={() => navigate('login')} className="btn-primary text-sm">
                  Começar
                </button>
              </div>
            </div>
          </header>
          <Landing onNavigate={navigate} />
        </div>
      ) : (
        <Layout currentRoute={route} onNavigate={navigate} acwr={acwr} onLogout={onLogout}>
          {renderPage()}
        </Layout>
      )}
    </ThemeProvider>
  )
}
