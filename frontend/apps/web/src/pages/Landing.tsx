import { useState, useEffect } from 'react'
import { ArrowRight, Play, Sparkles, FlaskConical, ScanLine, Activity, Dumbbell, Star } from 'lucide-react'

// mini-rota (preview do hero)
const routeD = 'M 6 30 C 30 8, 50 8, 70 22 S 110 40, 134 16 154 26'

// os 4 pilares — copy honesta, descreve o que o app DE FATO faz
const science = [
  { icon: FlaskConical, title: 'Apoiado pela Ciência',
    desc: 'Cada leitura vem de estudos revisados por pares — mais de 25 no sistema, e crescendo. O coach cita a fonte de cada recomendação, pra você conferir de onde veio.' },
  { icon: ScanLine, title: 'Visão Computacional (IA)',
    desc: 'Você filma correndo e a IA rastreia suas articulações, mede os ângulos e detecta os eventos da passada — apoio, voo e pisada — calculando cadência, tempo de contato e de voo. Tudo no seu aparelho.' },
  { icon: Activity, title: 'Biomecânica personalizada',
    desc: 'Cruzamos os dados do seu movimento com o seu contexto — histórico, hábitos e proporções do corpo — pra achar os parâmetros ideais pra você, não uma média genérica.' },
  { icon: Dumbbell, title: 'Algoritmo Corretivo',
    desc: 'Do que está fora do ideal, apontamos o que melhorar e sugerimos exercícios específicos — cada um amparado por pesquisa.' },
]

// Clipes de ATLETAS INDIVIDUAIS correndo, em rotação (crossfade) por trás do texto.
// Fonte: Pexels — licença comercial, SEM atribuição obrigatória (crédito é cortesia).
// Créditos dos autores em public/videos/CREDITS.txt.
const HERO_VIDEOS = ['/videos/run1.mp4', '/videos/run2.mp4', '/videos/run3.mp4', '/videos/run4.mp4']

// DEPOIMENTOS — PLACEHOLDER (o app ainda não tem usuários reais). Nomes, textos e FOTOS são
// só EXEMPLOS pra visualizar a seção. As fotos são retratos livres do Pexels (uso comercial),
// mas NÃO representam pessoas reais que disseram isso — substituir por depoimentos REAIS antes
// de publicar (estampar gente inventada com foto seria enganoso).
const TESTIMONIALS = [
  { name: 'Marina R.', role: 'Corredora amadora', photo: '/avatars/av1.jpg',
    quote: 'A análise de vídeo mostrou que minha passada era longa demais. Ajustei a cadência e a dor no joelho sumiu.' },
  { name: 'Diego F.', role: 'Maratonista', photo: '/avatars/av2.jpg',
    quote: 'Finalmente um coach que explica o porquê e ainda cita o estudo. Larguei a dica aleatória de rede social.' },
  { name: 'Camila S.', role: 'Triatleta', photo: '/avatars/av5.jpg',
    quote: 'O plano corretivo me deu exercícios certeiros pro quadril. Em 3 semanas a corrida ficou mais leve.' },
  { name: 'Rafael T.', role: 'Atleta de HYROX', photo: '/avatars/av4.jpg',
    quote: 'Ver meu esqueleto correndo é surreal. Entendi minha biomecânica sem ir num laboratório caro.' },
  { name: 'Beatriz L.', role: 'Corredora de rua', photo: '/avatars/av3.jpg',
    quote: 'A prontidão diária me segurou de treinar forte num dia que meu corpo pedia descanso. Zero lesão desde então.' },
  { name: 'Lucas M.', role: 'Dev que corre', photo: '/avatars/av6.jpg',
    quote: 'Privacidade de verdade: meus dados não saem do meu computador. Isso pra mim vale ouro.' },
]

function TestimonialCard({ t }: { t: (typeof TESTIMONIALS)[number] }) {
  return (
    <div className="card w-[300px] shrink-0">
      <div className="flex gap-0.5 mb-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Star key={i} size={14} className="text-accent-yellow" fill="currentColor" />
        ))}
      </div>
      <p className="text-sm text-text-secondary leading-relaxed">"{t.quote}"</p>
      <div className="flex items-center gap-3 mt-4">
        <img src={t.photo} alt="" loading="lazy"
          className="w-9 h-9 rounded-full object-cover shrink-0 ring-2 ring-brand/20" />
        <div>
          <p className="text-sm font-semibold">{t.name}</p>
          <p className="text-xs text-text-muted">{t.role}</p>
        </div>
      </div>
    </div>
  )
}

export default function Landing({ onNavigate }: { onNavigate: (r: string) => void }) {
  const [vid, setVid] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setVid(v => (v + 1) % HERO_VIDEOS.length), 6500)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="min-h-[calc(100vh-4rem)]">
      {/* Hero em VÍDEO: atletas correndo em rotação, com a frase por cima */}
      <section className="relative overflow-hidden min-h-[560px] md:min-h-[660px] flex items-center">
        {/* camadas de vídeo (crossfade) + escurecedor pro texto ler. bg-black = fallback se o vídeo não carregar */}
        <div className="absolute inset-0 z-0 bg-black">
          {HERO_VIDEOS.map((src, i) => (
            <video key={src} src={src} autoPlay muted loop playsInline
              className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-1000 ${i === vid ? 'opacity-100' : 'opacity-0'}`} />
          ))}
          <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/60 to-black/25" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
          {/* crédito de cortesia (Pexels não exige atribuição) */}
          <p className="absolute bottom-2 right-3 text-[10px] text-white/40">
            Vídeos via <a href="https://www.pexels.com" target="_blank" rel="noreferrer" className="underline hover:text-white/70">Pexels</a>
          </p>
        </div>

        {/* Texto sobreposto, colado na borda ESQUERDA (o flex items-center da section centraliza na vertical) */}
        <div className="relative z-10 w-full pl-4 md:pl-6 lg:pl-8 pr-4">
          <div className="max-w-md text-white">
            <span className="inline-flex items-center gap-2 text-xs font-medium text-white/85 bg-white/10 border border-white/20 rounded-full px-3 py-1 backdrop-blur">
              <span className="w-1.5 h-1.5 rounded-full bg-brand" /> Corrida · HYROX · CrossFit
            </span>
            <h1 className="font-display font-bold uppercase mt-4 text-3xl md:text-4xl lg:text-5xl tracking-tight leading-[0.98] drop-shadow-lg">
              A IA que <span className="text-brand">enxerga</span><br />a sua corrida
            </h1>
            <p className="mt-6 text-lg md:text-xl text-white/80 max-w-xl text-balance drop-shadow">
              Do relógio ao vídeo: analisamos cada passada, achamos a causa-raiz e devolvemos um
              plano com base científica. 100% no seu aparelho.
            </p>
            <div className="flex flex-wrap gap-3 mt-9">
              <button onClick={() => onNavigate('dashboard')} className="btn-primary text-base px-8 py-4">
                Começar grátis <ArrowRight size={18} />
              </button>
              <button className="inline-flex items-center gap-2 rounded-xl font-semibold px-8 py-4 text-base text-white border border-white/40 hover:bg-white/10 transition-colors">
                <Play size={18} /> Ver demo
              </button>
            </div>
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

      {/* Ciência / análise de movimento — os 4 pilares */}
      <section className="max-w-6xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <span className="inline-flex items-center gap-2 text-xs font-medium text-brand bg-brand/10 border border-brand/20 rounded-full px-3 py-1">
            <Sparkles size={13} /> Análise de movimento
          </span>
          <h2 className="text-2xl md:text-3xl font-bold mt-4">Biomecânica de qualidade laboratorial, no seu bolso</h2>
          <p className="text-text-secondary mt-3 max-w-2xl mx-auto">
            A IA vê o seu movimento e traduz em causa-raiz — pra você agir antes que a dor vire lesão.
          </p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {science.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="card-hover">
              <div className="w-10 h-10 rounded-xl bg-brand/10 flex items-center justify-center mb-3">
                <Icon size={20} className="text-brand" />
              </div>
              <h3 className="font-semibold mb-1.5">{title}</h3>
              <p className="text-sm text-text-secondary leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Depoimentos — carrossel infinito (marquee). PLACEHOLDER até termos usuários reais. */}
      <section className="py-16 overflow-hidden">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-2">Quem corre com a gente</h2>
        <p className="text-text-secondary text-center mb-10 px-4">O que os atletas dizem depois de ver a própria corrida.</p>
        <div className="marquee-pause relative">
          <div className="flex gap-4 w-max animate-marquee px-2">
            {[...TESTIMONIALS, ...TESTIMONIALS].map((t, i) => <TestimonialCard key={i} t={t} />)}
          </div>
          {/* bordas em fade pro loop parecer contínuo */}
          <div className="pointer-events-none absolute inset-y-0 left-0 w-16 md:w-28 bg-gradient-to-r from-[var(--surface-bg)] to-transparent" />
          <div className="pointer-events-none absolute inset-y-0 right-0 w-16 md:w-28 bg-gradient-to-l from-[var(--surface-bg)] to-transparent" />
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
