import { useState, useCallback, useEffect } from 'react'
import * as Tooltip from '@radix-ui/react-tooltip'
import { ThemeProvider } from './components/layout/ThemeProvider'
import Layout from './components/layout/Layout'
import Landing from './pages/Landing'
import MovementAnalysis from './pages/MovementAnalysis'
import Login from './pages/Login'
import ThemeToggle from './components/layout/ThemeToggle'
import { api, session } from '@strideredge/core'

type Route = 'landing' | 'login' | 'video'

// Rota <-> URL: digitar/copiar /movimento passa pela MESMA guarda — sem sessão, qualquer
// caminho protegido cai no /login (nada de entrar pela URL).
const PATHS: Record<Route, string> = {
  landing: '/', login: '/login', video: '/movimento',
}
const PUBLIC: Route[] = ['landing', 'login']
const routeFromPath = (path: string): Route =>
  (Object.entries(PATHS).find(([, p]) => p === path)?.[0] as Route) ?? 'landing'

export default function App() {
  // Sessão: token (conta) ou modo convidado (local). Sem sessão -> landing pública.
  const [authed, setAuthed] = useState(() => !!(session.get() || localStorage.getItem('se_guest')))

  // Guarda de entrada: resolve a rota INICIAL a partir da URL digitada/colada
  const [route, setRouteState] = useState<Route>(() => {
    const wanted = routeFromPath(window.location.pathname)
    const initial = !authed && !PUBLIC.includes(wanted) ? 'login'
      : authed && PUBLIC.includes(wanted) ? 'video'   // logado não volta pro marketing
      : wanted
    window.history.replaceState(null, '', PATHS[initial])
    return initial
  })

  const setRoute = useCallback((r: Route) => {
    setRouteState(r)
    if (window.location.pathname !== PATHS[r]) window.history.pushState(null, '', PATHS[r])
  }, [])

  const navigate = useCallback((r: string) => {
    if (!Object.keys(PATHS).includes(r)) return
    // visitante só circula entre landing e login; o app pede sessão
    if (!authed && !PUBLIC.includes(r as Route)) { setRoute('login'); return }
    setRoute(r as Route)
  }, [authed, setRoute])

  // Voltar/avançar do navegador passam pela mesma guarda
  useEffect(() => {
    const onPop = () => {
      const wanted = routeFromPath(window.location.pathname)
      if (!authed && !PUBLIC.includes(wanted)) { setRoute('login'); return }
      setRouteState(wanted)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [authed, setRoute])

  // Credencial de verdade, não só cache: token no localStorage é validado no backend
  // (/auth/me). Token forjado/expirado -> sessão derrubada -> login.
  useEffect(() => {
    if (!session.get()) return
    api.auth.me().catch(() => {
      session.clear()
      if (!localStorage.getItem('se_guest')) {
        setAuthed(false)
        setRoute('login')
      }
    })
  }, [setRoute])

  const onAuthed = useCallback((user: { name: string } | null) => {
    if (user === null) localStorage.setItem('se_guest', '1')   // modo local
    setAuthed(true)
    setRoute('video')
  }, [setRoute])

  const onLogout = useCallback(() => {
    session.clear()
    localStorage.removeItem('se_guest')
    setAuthed(false)
    setRoute('landing')
  }, [setRoute])

  const renderPage = () => {
    switch (route) {
      case 'landing':
        return <Landing onNavigate={navigate} />
      case 'video':
        return <MovementAnalysis onNavigate={navigate} />
      default:
        return <MovementAnalysis onNavigate={navigate} />
    }
  }

  const isLanding = route === 'landing'
  if (route === 'login') return <ThemeProvider><Login onAuthed={onAuthed} onBack={() => setRoute('landing')} /></ThemeProvider>

  return (
    <ThemeProvider>
      <Tooltip.Provider delayDuration={150} skipDelayDuration={400}>
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
                <ThemeToggle />
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
        <Layout currentRoute={route} onNavigate={navigate} onLogout={onLogout}>
          {renderPage()}
        </Layout>
      )}
      </Tooltip.Provider>
    </ThemeProvider>
  )
}
