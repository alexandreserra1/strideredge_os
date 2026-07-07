import { ArrowRight, Brain, Trophy, Map, Zap, Play, Sparkles } from 'lucide-react'
import AppFrame from '../components/ui/AppFrame'
import shotDashboard from '../assets/screens/dashboard.png'
import shotMapa from '../assets/screens/mapa.png'
import shotAnalise from '../assets/screens/analise.png'

const features = [
  { icon: Brain, title: 'Coach que explica o porquê', desc: 'Análise com embasamento científico — e a fonte citada. Nada de dica genérica de rede social.' },
  { icon: Map, title: 'Sua passada no mapa', desc: 'Veja metro a metro onde você segurou firme e onde a fadiga chegou — em cores, na sua rota real.' },
  { icon: Trophy, title: 'Previsão de prova', desc: 'Descubra do que você é capaz hoje nos 5K, 10K, meia e maratona — e veja esse teto subir.' },
  { icon: Zap, title: 'Prontidão diária', desc: 'Um semáforo simples diz se hoje é dia de acelerar ou de recuperar — antes que a lesão avise.' },
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
              Seu relógio coleta os dados. A gente transforma em evolução: um coach de IA que
              analisa cada treino, aponta o que travou e diz o próximo passo. Privado de verdade.
            </p>
            <div className="flex flex-wrap justify-center md:justify-start gap-3 mt-9">
              <button onClick={() => onNavigate('dashboard')} className="btn-primary text-base px-8 py-4">
                Começar grátis <ArrowRight size={18} />
              </button>
              <button className="btn-ghost text-base px-8 py-4"><Play size={18} /> Ver demo</button>
            </div>
          </div>

          {/* Preview: PRINT REAL do produto (o app é o marketing) */}
          <div className="flex-1 w-full max-w-2xl relative">
            <div className="absolute -inset-8 -z-10 rounded-[40px] opacity-60"
              style={{ background: 'radial-gradient(50% 50% at 50% 50%, var(--brand-soft), transparent 70%)' }} />
            <AppFrame src={shotDashboard} alt="Dashboard do StriderEdge com prontidão, previsões e volume"
              className="animate-slide-up" />
            {/* chips flutuantes por cima do print */}
            <div className="absolute -left-4 top-16 glass rounded-2xl px-4 py-3 shadow-xl animate-float hidden md:block">
              <p className="text-[10px] text-text-secondary uppercase tracking-wider">Prontidão</p>
              <p className="text-xl font-black tabular-nums">0.96 <span className="text-xs font-semibold text-accent-green">Ótima</span></p>
            </div>
            <div className="absolute -right-3 bottom-10 glass rounded-2xl px-4 py-3 shadow-xl max-w-[240px] hidden md:block">
              <p className="text-[10px] text-brand uppercase tracking-wider font-semibold flex items-center gap-1">
                <Sparkles size={10} /> Coach
              </p>
              <p className="text-xs text-text-secondary leading-snug mt-1">
                "Pacing consistente até o km 6 — inclui tiros na cadência alvo."
              </p>
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

      {/* Vitrine: o produto de verdade, sem mock */}
      <section className="max-w-6xl mx-auto px-4 py-16">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-3">Você por dentro, de verdade</h2>
        <p className="text-text-secondary text-center mb-12 max-w-xl mx-auto">
          Telas reais do produto — cada treino vira mapa, análise e um plano de ação.
        </p>
        <AppFrame src={shotMapa} alt="Mapa real com a rota colorida pela cadência" />
        <div className="grid md:grid-cols-2 gap-6 mt-6 items-center">
          <AppFrame src={shotAnalise} alt="Painel de risco de lesão e calendário de treinos" />
          <div className="px-2">
            <h3 className="text-xl font-bold mb-4">Saúde antes de recorde</h3>
            <ul className="space-y-3 text-sm text-text-secondary">
              <li className="flex gap-3"><span className="text-accent-green mt-0.5">✓</span> Risco de lesão monitorado todos os dias — carga, cadência, fadiga e progressão.</li>
              <li className="flex gap-3"><span className="text-accent-green mt-0.5">✓</span> Calendário de treinos interativo: o mês inteiro num olhar.</li>
              <li className="flex gap-3"><span className="text-accent-green mt-0.5">✓</span> Review do coach por treino, com recomendação e fonte científica.</li>
              <li className="flex gap-3"><span className="text-accent-green mt-0.5">✓</span> Tudo privado: seus dados não saem da sua máquina.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Como funciona */}
      <section className="max-w-4xl mx-auto px-4 py-16">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-12">Como funciona</h2>
        <div className="space-y-6">
          {[
            { step: '01', title: 'Conecte', desc: 'Traga os treinos do seu relógio em um clique. Tudo fica com você — nada vai pra nuvem.' },
            { step: '02', title: 'A gente disseca', desc: 'Cada segundo do treino vira leitura: passada, coração, subidas, fadiga. Sem planilha, sem esforço.' },
            { step: '03', title: 'Receba o veredito', desc: 'O que foi bem, o que travou e exatamente o que fazer no próximo treino — direto ao ponto.' },
            { step: '04', title: 'Evolua com segurança', desc: 'Prontidão diária e previsões de prova guiam o ritmo: forte na hora certa, descanso antes da lesão.' },
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
