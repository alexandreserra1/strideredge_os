import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Sparkles, Moon, Sun } from 'lucide-react'
import { api, session } from '@strideredge/core'
import type { AuthUser } from '@strideredge/core'
import { useTheme } from '../components/layout/ThemeProvider'
import AppFrame from '../components/ui/AppFrame'
import shotDashboard from '../assets/screens/dashboard.png'
import shotMapa from '../assets/screens/mapa.png'
import shotAnalise from '../assets/screens/analise.png'

// O produto é a imagem: prints REAIS do app (autêntico > foto de banco de imagem)
const SLIDES = [
  { img: shotDashboard, alt: 'Dashboard com prontidão e previsões',
    title: 'Seu desempenho num olhar', line: 'Prontidão diária, previsão de prova e volume — calculados dos seus treinos reais.',
    from: '#6E56F7', to: '#38BDF8' },
  { img: shotMapa, alt: 'Mapa com a rota colorida pela cadência',
    title: 'Sua rota, metro a metro', line: 'O mapa mostra onde a passada segurou firme e onde a fadiga chegou.',
    from: '#FF8A4C', to: '#FB5E7E' },
  { img: shotAnalise, alt: 'Painel de risco de lesão',
    title: 'Saúde antes de recorde', line: 'Risco de lesão monitorado com ciência — saiba quando acelerar e quando recuperar.',
    from: '#34D399', to: '#38BDF8' },
]

declare global {
  interface Window { google?: any }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

export default function Login({ onAuthed, onBack }: {
  onAuthed: (user: AuthUser | null) => void   // null = modo convidado (local)
  onBack: () => void
}) {
  const { theme, setTheme } = useTheme()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [slide, setSlide] = useState(0)
  const googleRef = useRef<HTMLDivElement>(null)

  // carrossel: troca de esporte a cada 3.5s
  useEffect(() => {
    const t = setInterval(() => setSlide(s => (s + 1) % SLIDES.length), 3500)
    return () => clearInterval(t)
  }, [])

  // Google Identity Services: só quando há client id configurado
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !googleRef.current) return
    const s = document.createElement('script')
    s.src = 'https://accounts.google.com/gsi/client'
    s.async = true
    s.onload = () => {
      window.google?.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (resp: { credential: string }) => {
          try {
            setBusy(true)
            const out = await api.auth.google(resp.credential)
            session.set(out.token)
            onAuthed(out.user)
          } catch {
            setError('Login com Google falhou — tenta de novo?')
          } finally {
            setBusy(false)
          }
        },
      })
      window.google?.accounts.id.renderButton(googleRef.current, {
        theme: 'outline', size: 'large', width: 320, text: 'continue_with',
      })
    }
    document.head.appendChild(s)
    return () => { s.remove() }
  }, [onAuthed])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (mode === 'register' && password !== confirm) {
      setError('As senhas não conferem.')
      return
    }
    setBusy(true)
    try {
      const out = mode === 'register'
        ? await api.auth.register(name, email, password)
        : await api.auth.login(email, password)
      session.set(out.token)
      onAuthed(out.user)
    } catch (err) {
      const msg = err instanceof Error ? err.message : ''
      setError(
        msg.includes('409') || msg.includes('cadastro') ? 'Este e-mail já tem cadastro — tenta entrar.'
        : msg.includes('401') || msg.includes('incorretos') ? 'E-mail ou senha incorretos.'
        : msg.includes('422') ? 'Confere o e-mail e uma senha com 8+ caracteres.'
        : 'Não consegui falar com o servidor — a API está no ar?')
    } finally {
      setBusy(false)
    }
  }

  const slideData = SLIDES[slide]

  return (
    <div className="min-h-screen bg-surface grid lg:grid-cols-2">
      {/* Painel esquerdo: o PRODUTO de verdade, um print por slide */}
      <div className="hidden lg:flex flex-col justify-between p-10 relative overflow-hidden"
        style={{ background: `linear-gradient(135deg, ${slideData.from}, ${slideData.to})`, transition: 'background 900ms ease' }}>
        <button onClick={onBack} className="flex items-center gap-2 text-sm text-white/80 hover:text-white transition-colors w-fit">
          <ArrowLeft size={16} /> Voltar
        </button>

        <div key={slide} className="animate-fade-in">
          <AppFrame src={slideData.img} alt={slideData.alt} className="shadow-2xl mb-8 max-w-lg" />
          <h2 className="text-3xl font-black tracking-tight mb-2 text-white">{slideData.title}</h2>
          <p className="text-base text-white/85 max-w-md leading-relaxed">{slideData.line}</p>
        </div>

        <div className="flex items-center gap-2">
          {SLIDES.map((_, i) => (
            <button key={i} onClick={() => setSlide(i)} aria-label={`Slide ${i + 1}`}
              className="h-1.5 rounded-full transition-all duration-500"
              style={{ width: i === slide ? 28 : 10, background: i === slide ? '#fff' : 'rgba(255,255,255,0.4)' }} />
          ))}
        </div>
      </div>

      {/* Painel direito: formulário */}
      <div className="flex items-center justify-center p-6 relative">
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          title={theme === 'dark' ? 'Modo claro' : 'Modo escuro'}
          className="absolute top-5 right-5 p-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-surface-200 transition-all">
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <div className="w-full max-w-sm">
          <button onClick={onBack} className="lg:hidden flex items-center gap-2 text-sm text-text-secondary mb-8">
            <ArrowLeft size={16} /> Voltar
          </button>

          <div className="flex items-center gap-2.5 mb-8">
            <span className="grid place-items-center w-9 h-9 rounded-xl bg-brand text-brand-ink font-black">S</span>
            <span className="text-xl font-bold tracking-tight">Strider<span className="text-brand">Edge</span></span>
          </div>

          <h1 className="text-2xl font-bold mb-1">{mode === 'login' ? 'Bem-vindo de volta' : 'Criar sua conta'}</h1>
          <p className="text-sm text-text-secondary mb-6">
            {mode === 'login' ? 'Entra pra ver seus treinos e o coach.' : 'Grátis, local e seus dados são só seus.'}
          </p>

          <form onSubmit={submit} className="space-y-3">
            {mode === 'register' && (
              <input value={name} onChange={e => setName(e.target.value)} placeholder="Nome"
                autoComplete="name" required
                className="w-full px-4 py-3 rounded-xl bg-surface-200 border border-border-light focus:border-brand focus:outline-none text-sm" />
            )}
            <input value={email} onChange={e => setEmail(e.target.value)} placeholder="E-mail" type="email"
              autoComplete="email" required
              className="w-full px-4 py-3 rounded-xl bg-surface-200 border border-border-light focus:border-brand focus:outline-none text-sm" />
            <input value={password} onChange={e => setPassword(e.target.value)} placeholder="Senha (8+ caracteres)"
              type="password" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} required minLength={8}
              className="w-full px-4 py-3 rounded-xl bg-surface-200 border border-border-light focus:border-brand focus:outline-none text-sm" />
            {mode === 'register' && (
              <input value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="Confirmar senha"
                type="password" autoComplete="new-password" required minLength={8}
                className={`w-full px-4 py-3 rounded-xl bg-surface-200 border focus:outline-none text-sm
                  ${confirm && confirm !== password ? 'border-accent-red' : 'border-border-light focus:border-brand'}`} />
            )}

            {error && <p className="text-xs text-accent-red">{error}</p>}

            <button type="submit" disabled={busy} className="btn-primary w-full py-3 text-sm justify-center">
              {busy ? 'Entrando…' : mode === 'login' ? 'Entrar' : 'Criar conta'}
            </button>
          </form>

          <div className="flex items-center gap-3 my-5">
            <span className="flex-1 h-px bg-border-light" />
            <span className="text-[10px] text-text-muted uppercase tracking-wider">ou</span>
            <span className="flex-1 h-px bg-border-light" />
          </div>

          {GOOGLE_CLIENT_ID ? (
            <div ref={googleRef} className="flex justify-center" />
          ) : (
            <button disabled title="Defina VITE_GOOGLE_CLIENT_ID (front) e GOOGLE_CLIENT_ID (API) para ativar"
              className="w-full py-3 rounded-xl border border-border-light text-sm text-text-muted cursor-not-allowed">
              Continuar com Google — não configurado
            </button>
          )}

          {import.meta.env.DEV && (
            <button onClick={() => onAuthed(null)}
              className="w-full mt-3 py-3 rounded-xl border border-dashed border-border-medium text-sm text-text-secondary hover:text-text-primary hover:border-border-medium transition-colors flex items-center justify-center gap-2">
              <Sparkles size={14} /> Continuar sem conta (só em desenvolvimento)
            </button>
          )}

          <p className="text-xs text-text-secondary text-center mt-6">
            {mode === 'login' ? 'Ainda não tem conta?' : 'Já tem conta?'}{' '}
            <button onClick={() => { setMode(m => m === 'login' ? 'register' : 'login'); setError('') }}
              className="text-brand font-medium hover:underline">
              {mode === 'login' ? 'Criar agora' : 'Entrar'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
