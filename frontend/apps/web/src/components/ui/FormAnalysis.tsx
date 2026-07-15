import { useCallback, useEffect, useRef, useState } from 'react'
import { Clapperboard, Info, Loader2, Upload } from 'lucide-react'
import { api } from '@strideredge/core'
import type { FormAnalysis as Analysis, FormPlan } from '@strideredge/core'
import InfoHint from './InfoHint'

// Semáforo por métrica (faixas da literatura de corrida; explicação vai junto — didático)
const METRIC_DEFS = [
  {
    key: 'cadence_spm' as const, label: 'Cadência', unit: 'spm',
    level: (v: number) => (v >= 170 ? 'ok' : v >= 160 ? 'warn' : 'risk'),
    why: 'Passos por minuto medidos PELA CÂMERA. Alvo ≥170; abaixo de 160 aumenta a carga de impacto por passo.',
  },
  {
    key: 'asymmetry_pct' as const, label: 'Assimetria E/D', unit: '%',
    level: (v: number) => (v < 10 ? 'ok' : v < 20 ? 'warn' : 'risk'),
    why: 'Diferença de amplitude entre as pernas. <10% é normal; acima disso, um lado trabalha mais — fadiga ou compensação.',
  },
  {
    key: 'vertical_oscillation_pct' as const, label: 'Oscilação vertical', unit: '% da perna',
    level: (v: number) => (v < 8 ? 'ok' : v < 12 ? 'warn' : 'risk'),
    why: 'Quanto o quadril sobe e desce. Menos oscilação = energia indo pra FRENTE, não pra cima.',
  },
  {
    key: 'knee_contact_deg' as const, label: 'Joelho no apoio', unit: '°',
    level: (v: number) => (v < 168 ? 'ok' : v < 174 ? 'warn' : 'risk'),
    why: 'Flexão do joelho no instante em que o pé toca o chão (o arco CIANO no vídeo). Perna muito reta (>174°) = passada longa demais, impacto direto na articulação. Um leve dobrar amortece.',
  },
  {
    key: 'hip_contact_deg' as const, label: 'Quadril no apoio', unit: '°',
    level: (_v: number) => 'ok',    // referência, sem faixa de risco firme na literatura aberta
    why: 'Abertura tronco↔coxa no apoio (o arco ÂMBAR no vídeo). Mostra o quanto você projeta a coxa — leitura de amplitude, não de risco.',
  },
  {
    key: 'trunk_lean_deg' as const, label: 'Inclinação do tronco', unit: '°',
    level: (v: number) => (v >= 4 && v <= 14 ? 'ok' : v < 4 || v <= 20 ? 'warn' : 'risk'),
    why: 'Inclinação do tronco vs. a vertical (a linha de prumo no vídeo). Uma leve inclinação pra FRENTE (~5–12°) aproveita a gravidade; correr ereto freia a cada passo, e muito inclinado sobrecarrega a lombar.',
  },
  {
    key: 'ground_contact_ms' as const, label: 'Contato com o solo', unit: 'ms',
    level: (v: number) => (v <= 250 ? 'ok' : v <= 300 ? 'warn' : 'risk'),
    why: 'Tempo que o pé fica no chão a cada passo. Menos tempo = passada mais elástica e rápida. Corredores eficientes ficam em torno de 200–250 ms.',
  },
  {
    key: 'flight_ms' as const, label: 'Tempo de voo', unit: 'ms',
    level: (_v: number) => 'ok',
    why: 'Tempo com os dois pés no ar a cada passo. Mais voo (com contato curto) indica boa fase de propulsão — leitura de elasticidade, não de risco.',
  },
  // --- plano frontal (aparecem só na análise de FRENTE) ---
  {
    key: 'pelvic_drop_deg' as const, label: 'Queda pélvica', unit: '°',
    level: (v: number) => (v < 10 ? 'ok' : v < 15 ? 'warn' : 'risk'),
    why: 'Quanto a bacia cai pro lado a cada apoio (vista de frente). Acima de ~10° é sinal de quadril fraco — puxa o joelho pra dentro e sobrecarrega patela e banda IT.',
  },
  {
    key: 'knee_valgus_deg' as const, label: 'Valgo de joelho', unit: '°',
    level: (v: number) => (v < 10 ? 'ok' : v < 15 ? 'warn' : 'risk'),
    why: 'O quanto o joelho "cai pra dentro" no apoio (FPPA, vista de frente). Valgo alto é um dos padrões mais ligados a dor no joelho na corrida.',
  },
]
const LEVEL_COLOR: Record<string, string> = { ok: '#34D399', warn: '#FBBF24', risk: '#F87171' }
// Faixa de risco de lesão (relativa, aterrada na literatura)
const RISK_COLOR: Record<string, string> = {
  baixo: '#34D399', moderado: '#FBBF24', elevado: '#FB923C', alto: '#F87171',
}

// Códigos PMC não dizem nada pro atleta — mostramos um nome legível (a fonte real fica no hover)
const SOURCE_LABEL: Record<string, string> = {
  PMC12440572: 'Cadência e prevenção de lesão',
  PMC10761631: 'Reeducação de cadência com metrônomo',
  PMC6883353: '+10% de cadência e dor no joelho',
  PMC9441414: 'Efeito da frequência de passos',
  PMC3944563: 'Tempo de contato e economia',
  PMC7241633: 'Simetria de contato e economia',
  PMC11127892: 'Biomecânica e economia de corrida',
  PMC11135760: 'Inclinação do tronco e economia',
  PMC7734358: 'Padrões de pisada (revisão)',
  PMC5528965: 'Antepé × calcanhar no impacto',
  PMC9653533: 'Força × pliometria na corrida',
  PMC3070501: 'Fortalecimento de quadril',
  PMC12372021: 'Exercícios de quadril com banda',
  // fontes sem PMC (têm DOI/PubMed — reais e citáveis; o id completo fica no hover)
  'DOI:10.2519/jospt.2015.6019': 'Padrões de pisada (JOSPT)',
  'DOI:10.2519/jospt.2015.5091': 'Força de quadril e dor no joelho',
  'DOI:10.2519/jospt.2018.7365': 'Fortalecer quadril + joelho',
  'PMID:34537800': 'Inclinar o tronco e o joelho',
  'Effects of Plyometric Jump Training on Running Economy in Endurance Runners': 'Pliometria e economia',
}
const sourceLabel = (id: string) => SOURCE_LABEL[id] ?? 'Estudo revisado por pares'

export default function FormAnalysisCard({ modality = 'run', view = 'lateral' }: {
  modality?: string
  view?: string   // 'lateral' | 'frontal' — define o conjunto de métricas do motor
} = {}) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [plan, setPlan] = useState<FormPlan | null>(null)
  const [planLoading, setPlanLoading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // última análise enviada
  useEffect(() => {
    api.form.list().then(list => setAnalysis(list[0] ?? null)).catch(() => {})
  }, [])

  const genPlan = useCallback(async () => {
    if (!analysis) return
    setPlanLoading(true)
    try { setPlan(await api.form.coach(analysis.analysis_id)) }
    catch { setError('Não consegui gerar o plano — o coach local está no ar?') }
    finally { setPlanLoading(false) }
  }, [analysis])

  // enquanto processa, consulta a cada 3s
  useEffect(() => {
    if (analysis?.status !== 'processing') return
    const t = setInterval(() => {
      api.form.get(analysis.analysis_id).then(setAnalysis).catch(() => {})
    }, 3000)
    return () => clearInterval(t)
  }, [analysis?.status, analysis?.analysis_id])

  const onFile = useCallback(async (file: File) => {
    setError('')
    setUploading(true)
    try {
      const out = await api.form.upload(file, { modality, view })
      setAnalysis({ analysis_id: out.analysis_id, activity_id: null, status: 'processing',
                    video_path: null, metrics: null, error: null, created_at: '' })
    } catch {
      setError('Falha no upload — a API está no ar?')
    } finally {
      setUploading(false)
    }
  }, [modality, view])

  return (
    <div className="card overflow-hidden ring-1 ring-brand/20">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Clapperboard size={15} className="text-brand" /> Análise de Forma
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-brand/12 text-brand">A IA vendo seu movimento</span>
        </h3>
        {analysis?.status === 'done' && (
          <button onClick={() => fileRef.current?.click()} className="btn-ghost text-xs">Nova análise</button>
        )}
      </div>

      <input ref={fileRef} type="file" accept="video/*" className="hidden"
        onChange={e => e.target.files?.[0] && onFile(e.target.files[0])} />

      {!analysis && (
        <button onClick={() => fileRef.current?.click()} disabled={uploading}
          className="w-full rounded-xl border-2 border-dashed border-border-medium hover:border-brand/50 transition-colors p-8 text-center">
          <Upload size={22} className="mx-auto text-text-secondary mb-2" />
          <p className="text-sm font-medium">{uploading ? 'Enviando…' : 'Enviar vídeo do treino'}</p>
          <p className="text-xs text-text-muted mt-1">
            Filme de LADO, corpo inteiro no quadro, 20–30s (esteira funciona ótimo).
            A IA desenha seu esqueleto e mede cadência, assimetria e oscilação — 100% local.
          </p>
        </button>
      )}

      {analysis?.status === 'processing' && (
        <div className="flex items-center gap-3 p-5 rounded-xl bg-brand/[0.06] border border-brand/20">
          <Loader2 size={18} className="text-brand animate-spin" />
          <div>
            <p className="text-sm font-medium">Analisando seu movimento…</p>
            <p className="text-xs text-text-secondary">Pose estimation frame a frame no motor local (~1 min).</p>
          </div>
        </div>
      )}

      {analysis?.status === 'failed' && (
        <div className="p-4 rounded-xl bg-accent-red/10 border border-accent-red/20">
          <p className="text-sm text-accent-red">Não consegui analisar: {analysis.error}</p>
          <button onClick={() => fileRef.current?.click()} className="btn-ghost text-xs mt-2">Tentar outro vídeo</button>
        </div>
      )}

      {analysis?.status === 'done' && analysis.metrics && (
        <div className="animate-fade-in">
          {/* vídeo compacto e centralizado — é o produto, não pode disputar espaço com nada */}
          <div className="mx-auto max-w-sm">
            <video controls loop muted playsInline className="w-full rounded-xl border border-border-light bg-black"
              src={api.form.videoUrl(analysis.analysis_id)} />
            {/* legenda das cores dos arcos (o texto é de graça aqui; no vídeo fica só o arco) */}
            <div className="flex items-center justify-center gap-4 mt-2 text-[11px] text-text-secondary">
              <span className="flex items-center gap-1.5"><span className="w-3 h-1 rounded-full" style={{ background: '#78E8FF' }} /> ângulo do joelho</span>
              <span className="flex items-center gap-1.5"><span className="w-3 h-1 rounded-full" style={{ background: '#FFB259' }} /> ângulo do quadril</span>
            </div>
          </div>

          {!analysis.metrics.reliable && (
            <div className="rounded-xl bg-accent-yellow/10 border border-accent-yellow/25 p-3 mt-3">
              <p className="text-xs font-semibold text-accent-yellow flex items-center gap-1.5">
                <Info size={13} /> Análise pouco confiável
              </p>
              <p className="text-[11px] text-text-secondary mt-1 leading-snug">
                {analysis.metrics.quality_note ?? 'Filme de lado, com o corpo inteiro no quadro.'}
              </p>
            </div>
          )}

          {/* métricas em pílulas compactas — número na cara, explicação só no hover */}
          <div className="flex flex-wrap justify-center gap-2 mt-3">
            {METRIC_DEFS.map(def => {
              const v = analysis.metrics![def.key]
              if (v == null) return null
              const lv = def.level(v)
              return (
                <div key={def.key}
                  className="flex items-center gap-2 rounded-full bg-surface-200 border border-border-light pl-3 pr-2.5 py-1.5">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: LEVEL_COLOR[lv] }} />
                  <span className="text-[11px] text-text-secondary whitespace-nowrap">{def.label}</span>
                  <span className="text-xs font-bold tabular-nums" style={{ color: LEVEL_COLOR[lv] }}>
                    {Math.round(v * 10) / 10}<span className="text-[9px] font-medium ml-0.5">{def.unit}</span>
                  </span>
                  <InfoHint text={def.why} />
                </div>
              )
            })}
          </div>

          {/* padrão de pisada é texto, não número */}
          {analysis.metrics.foot_strike && (
            <div className="flex items-center justify-center gap-1.5 mt-3 text-[11px]">
              <span className="text-text-secondary">Pisada estimada:</span>
              <span className="font-semibold text-text-primary capitalize">{analysis.metrics.foot_strike}</span>
              <InfoHint text="Estimativa pela posição do tornozelo em relação ao joelho no apoio (o modelo não tem ponto no pé, então é uma inferência, não medida direta). Pisar com o pé muito à frente do corpo (calcanhar) aumenta o freio e o impacto." />
            </div>
          )}

          {/* DUAS cadências independentes — a câmera mede, o relógio confere (nenhuma altera a outra) */}
          <div className="flex items-center justify-center gap-2 mt-3">
            {analysis.metrics.cadence_spm != null && (
              <span className="rounded-full bg-brand/10 border border-brand/20 px-3 py-1 text-[11px] text-brand font-medium">
                Cadência: {Math.round(analysis.metrics.cadence_spm)} spm
              </span>
            )}
            <InfoHint text="A câmera calcula a cadência pela oscilação dos pés no vídeo — 100% no seu aparelho, sem sensor externo." />
          </div>

          <p className="text-[10px] text-text-muted flex items-center justify-center gap-1 mt-2">
            <Info size={10} /> Qualidade da detecção: {Math.round(analysis.metrics.detection_rate_pct)}% dos frames
          </p>

          {/* Algoritmo Corretivo: dos desvios -> exercícios citados (coach local + ciência) */}
          <div className="mt-4 pt-4 border-t border-border-light">
            {!plan ? (
              <button onClick={genPlan} disabled={planLoading}
                className="btn-primary text-sm w-full">
                {planLoading ? 'Montando seu plano…' : '✨ Gerar plano corretivo'}
              </button>
            ) : (
              <div className="space-y-3 animate-fade-in">
                <h4 className="text-sm font-semibold flex items-center gap-1.5">
                  Plano corretivo
                  <InfoHint text="Compara suas métricas com as faixas ideais (ajustadas ao seu perfil) e recomenda exercícios amparados por estudos — cada um com a fonte citada." />
                </h4>

                {/* Faixa de risco de lesão — RELATIVA, aterrada na literatura (não é probabilidade) */}
                {plan.risk && (
                  <div className="rounded-xl border p-3"
                    style={{ borderColor: RISK_COLOR[plan.risk.risk_band] + '55', background: RISK_COLOR[plan.risk.risk_band] + '12' }}>
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ background: RISK_COLOR[plan.risk.risk_band] }} />
                      <span className="text-xs font-semibold">Risco de lesão: <span className="capitalize">{plan.risk.risk_band}</span></span>
                      <InfoHint text={plan.risk.caveat} />
                    </div>
                    {plan.risk.factors.length > 0 && (
                      <p className="text-[10px] text-text-muted mt-1">
                        Puxado por: {plan.risk.factors.slice(0, 3).map(f => f.label).join(' · ')}
                      </p>
                    )}
                  </div>
                )}

                {plan.deviations.length === 0 && (
                  <p className="text-sm text-text-secondary leading-relaxed">{plan.verdict}</p>
                )}
                {plan.deviations.length > 0 && (
                  <div>
                    <h5 className="text-[11px] font-semibold uppercase tracking-wider mb-2 text-accent-orange">O que está te segurando</h5>
                    <ul className="space-y-2.5">
                      {plan.deviations.map(d => (
                        <li key={d.metric} className="flex items-start gap-2">
                          <span className="text-accent-orange mt-0.5 shrink-0">!</span>
                          <div>
                            <p className="text-xs text-text-primary leading-snug">{d.plain || d.label}</p>
                            <p className="text-[10px] text-text-muted mt-0.5">
                              {d.label}: {Math.round(d.value * 10) / 10}{d.unit} · ideal {d.side === 'alto' ? '≤ ' + d.hi : '≥ ' + d.lo}{d.unit}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {plan.actions.length > 0 && (
                  <PlanList title="O que fazer nos próximos treinos" items={plan.actions} color="#38BDF8" glyph="→" />
                )}
                {plan.citations.length > 0 && (
                  <div className="pt-1">
                    <p className="text-[10px] text-text-muted mb-1">Baseado em:</p>
                    <div className="flex flex-wrap gap-1.5">
                      {plan.citations.map((c, i) => (
                        <span key={i} title={c}
                          className="text-[10px] text-text-secondary bg-surface-200 border border-border-light px-2 py-0.5 rounded-full">
                          📚 {sourceLabel(c)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {error && <p className="text-xs text-accent-red mt-3">{error}</p>}
    </div>
  )
}

function PlanList({ title, items, color, glyph }: {
  title: string; items: string[]; color: string; glyph: string
}) {
  return (
    <div>
      <h5 className="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style={{ color }}>{title}</h5>
      <ul className="space-y-1.5">
        {items.map((s, i) => (
          <li key={i} className="text-xs text-text-muted flex items-start gap-2">
            <span className="mt-0.5 shrink-0" style={{ color }}>{glyph}</span>{s}
          </li>
        ))}
      </ul>
    </div>
  )
}
