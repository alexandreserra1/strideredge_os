import { useEffect, useRef, useState } from 'react'
import { Footprints, Dumbbell, Flame, HeartPulse, ArrowLeft, Sparkles } from 'lucide-react'
import { api, session } from '@strideredge/core'
import type { AuthUser } from '@strideredge/core'

// Cards de esporte que ficam passando no painel esquerdo (sem imagem externa:
// gradiente + ícone + frase — CSP/offline friendly)
const SPORTS = [
  { icon: Footprints, title: 'Corrida', line: 'Rota real, zonas de FC e o ponto onde a mecânica quebra.', from: '#6E56F7', to: '#38BDF8' },
  { icon: Flame, title: 'HYROX', line: 'As 8 stations com carga e transições — módulo dedicado.', from: '#FF8A4C', to: '#FB5E7E' },
  { icon: Dumbbell, title: 'Força', line: 'Séries, reps e FC por exercício direto do relógio.', from: '#34D399', to: '#38BDF8' },
  { icon: HeartPulse, title: 'Saúde', line: 'Risco de lesão com ciência citável — ACWR, cadência, durabilidade.', from: '#FB5E7E', to: '#6E56F7' },
]

declare global {
  interface Window { google?: any }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

export default function Login({ onAuthed, onBack }: {
  onAuthed: (user: AuthUser | null) => void   // null = modo convidado (local)
  onBack: () => void
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [slide, setSlide] = useState(0)
  const googleRef = useRef<HTMLDivElement>(null)

  // carrossel: troca de esporte a cada 3.5s
  useEffect(() => {
    const t = setInterval(() => setSlide(s => (s + 1) % SPORTS.length), 3500)
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

  const sport = SPORTS[slide]
  const SportIcon = sport.icon

  return (
    <div className="min-h-screen bg-surface grid lg:grid-cols-2">
      {/* Painel esquerdo: carrossel de esportes */}
      <div className="hidden lg:flex flex-col justify-between p-10 relative overflow-hidden"
        style={{ background: `linear-gradient(135deg, ${sport.from}22, ${sport.to}11)`, transition: 'background 800ms ease' }}>
        <button onClick={onBack} className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors w-fit">
          <ArrowLeft size={16} /> Voltar
        </button>

        <div key={slide} className="animate-fade-in">
          <div className="grid place-items-center w-20 h-20 rounded-3xl mb-6"
            style={{ background: `linear-gradient(135deg, ${sport.from}, ${sport.to})`, color: '#fff', boxShadow: `0 20px 60px ${sport.from}55` }}>
            <SportIcon size={40} />
          </div>
          <h2 className="text-4xl font-black tracking-tight mb-3">{sport.title}</h2>
          <p className="text-lg text-text-secondary max-w-sm leading-relaxed">{sport.line}</p>
        </div>

        <div className="flex items-center gap-2">
          {SPORTS.map((_, i) => (
            <button key={i} onClick={() => setSlide(i)} aria-label={`Slide ${i + 1}`}
              className="h-1.5 rounded-full transition-all duration-500"
              style={{ width: i === slide ? 28 : 10, background: i === slide ? sport.from : 'var(--border-medium)' }} />
          ))}
        </div>
      </div>

      {/* Painel direito: formulário */}
      <div className="flex items-center justify-center p-6">
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

          <button onClick={() => onAuthed(null)}
            className="w-full mt-3 py-3 rounded-xl border border-dashed border-border-medium text-sm text-text-secondary hover:text-text-primary hover:border-border-medium transition-colors flex items-center justify-center gap-2">
            <Sparkles size={14} /> Continuar sem conta (modo local)
          </button>

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
