import { ArrowRight, Brain, Trophy, Map, Zap, Play } from 'lucide-react'

const features = [
  { icon: Brain, title: 'Coach IA Local', desc: 'LLM local (Qwen 7B) + RAG com literatura científica. Dados seus, privados, sem nuvem.' },
  { icon: Map, title: 'Análise da Passada', desc: 'Kalman suaviza o GPS, FFT detecta irregularidade de cadência, semáforo no mapa.' },
  { icon: Trophy, title: 'Previsão de Prova', desc: 'Modelo de Riegel prediz seu potencial em 5K, 10K, meia e maratona.' },
  { icon: Zap, title: 'ACWR & Prontidão', desc: 'Carga aguda/crônica com semáforo — saiba quando treinar forte ou recuperar.' },
]

// mini-rota (preview do hero)
const routeD = 'M 6 30 C 30 8, 50 8, 70 22 S 110 40, 134 16 154 26'

export default function Landing({ onNavigate }: { onNavigate: (r: string) => void }) {
  return (
    <div className="min-h-[calc(100vh-4rem)]">
      {/* Hero */}
      <section className="relative py-16 md:py-24 overflow-hidden">
        <div className="absolute inset-0 -z-10 pointer-events-none"
          style={{ background: 'radial-gradient(60% 50% at 70% 0%, var(--brand-soft), transparent 70%)' }} />
        <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center gap-10 md:gap-14">
          {/* Texto */}
          <div className="flex-1 text-center md:text-left">
            <span className="inline-flex items-center gap-2 text-xs font-medium text-text-secondary bg-surface-200 border border-border-light rounded-full px-3 py-1">
              <span className="w-1.5 h-1.5 rounded-full bg-brand" /> Corrida · HYROX · CrossFit
            </span>
            <h1 className="mt-5 text-4xl md:text-6xl lg:text-7xl font-black tracking-tight leading-[1.05]">
              O coach de IA<br />que <span className="text-brand">corre com você</span>
            </h1>
            <p className="mt-6 text-lg md:text-xl text-text-muted max-w-xl mx-auto md:mx-0 text-balance">
              Transforme seus treinos em insights acionáveis — coach de IA local, feedback de voz
              em tempo real e planos adaptativos. Privacidade total, sem assinatura obrigatória.
            </p>
            <div className="flex flex-wrap justify-center md:justify-start gap-3 mt-9">
              <button onClick={() => onNavigate('dashboard')} className="btn-primary text-base px-8 py-4">
                Começar grátis <ArrowRight size={18} />
              </button>
              <button className="btn-ghost text-base px-8 py-4"><Play size={18} /> Ver demo</button>
            </div>
          </div>

          {/* Preview do produto (no lugar do mascote) */}
          <div className="flex-1 w-full max-w-md">
            <div className="glass rounded-3xl p-5 border border-border-light shadow-2xl animate-slide-up">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] text-text-secondary uppercase tracking-wider font-medium">Prontidão · ACWR</p>
                  <p className="text-4xl font-black tabular-nums leading-none mt-1">0.96</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-accent-green/15 text-accent-green">Ótima</span>
              </div>
              <div className="mt-3 h-2 rounded-full bg-surface-300 overflow-hidden">
                <div className="h-full w-[62%] rounded-full bg-gradient-to-r from-accent-green to-brand" />
              </div>

              <div className="grid grid-cols-3 gap-2 mt-5">
                {[['5K', '25:55'], ['10K', '54:01'], ['21K', '2:00']].map(([k, v]) => (
                  <div key={k} className="rounded-xl bg-surface-200 border border-border-light p-3 text-center">
                    <p className="text-[10px] text-text-secondary">{k}</p>
                    <p className="text-sm font-bold tabular-nums">{v}</p>
                  </div>
                ))}
              </div>

              <div className="mt-4 rounded-2xl bg-surface-200 border border-border-light p-4">
                <p className="text-[10px] text-text-secondary uppercase tracking-wider mb-2">Percurso · cadência</p>
                <svg viewBox="0 0 160 40" className="w-full h-16">
                  <path d={routeD} fill="none" stroke="#34D399" strokeWidth={3} strokeLinecap="round" />
                  <path d="M 70 22 S 110 40, 134 16" fill="none" stroke="#FB5E7E" strokeWidth={3} strokeLinecap="round" />
                  <circle cx={100} cy={31} r={4} fill="#6E56F7" className="animate-pulse-ring"
                    style={{ transformBox: 'fill-box', transformOrigin: 'center' } as React.CSSProperties} />
                  <circle cx={100} cy={31} r={3} fill="#6E56F7" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-4 py-16">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-12">Tudo que você precisa pra evoluir</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="card-hover p-6 flex flex-col gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand/10 flex items-center justify-center">
                <Icon size={20} className="text-brand" />
              </div>
              <h3 className="font-semibold text-text-primary">{title}</h3>
              <p className="text-sm text-text-secondary leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Como funciona */}
      <section className="max-w-4xl mx-auto px-4 py-16">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-12">Como funciona</h2>
        <div className="space-y-6">
          {[
            { step: '01', title: 'Conecte', desc: 'Importe seus .FIT da Garmin ou sincronize automaticamente. Tudo local.' },
            { step: '02', title: 'Analise', desc: 'Kalman + DTW + FFT no kernel Rust. DuckDB processa em milissegundos.' },
            { step: '03', title: 'Receba o veredito', desc: 'O coach IA (Qwen 7B + RAG) aponta fortes, fracos e o que fazer.' },
            { step: '04', title: 'Evolua', desc: 'ACWR, previsões e plano adaptativo guiam cada passo.' },
          ].map(({ step, title, desc }) => (
            <div key={step} className="flex items-start gap-4 p-4">
              <span className="text-2xl font-black text-brand shrink-0 w-10">{step}</span>
              <div>
                <h3 className="font-semibold text-lg">{title}</h3>
                <p className="text-sm text-text-secondary mt-1">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-3xl mx-auto px-4 py-16 text-center">
        <div className="card-hover p-10 border-brand/10">
          <h2 className="text-2xl md:text-3xl font-bold mb-4">Pronto pra correr?</h2>
          <p className="text-text-muted mb-8">Seus dados, seu coach, sua evolução. Sem assinatura obrigatória.</p>
          <button onClick={() => onNavigate('dashboard')} className="btn-primary text-base px-10 py-4">
            Começar agora <ArrowRight size={18} />
          </button>
        </div>
      </section>
    </div>
  )
}
