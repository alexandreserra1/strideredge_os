// Copy do instrumento OSTRC + rótulos de vocabulário. Presentation-only (o vocabulário controlado
// canônico — quais lesões existem — vem da API /injuries/taxonomy; aqui só o texto pt-BR).

export const REGION_LABELS: Record<string, string> = {
  joelho_frente: 'Joelho (frente)',
  joelho_lateral: 'Joelho (lateral)',
  canela: 'Canela',
  pe: 'Pé',
  tornozelo: 'Tornozelo',
  quadril: 'Quadril',
  coxa: 'Coxa',
}

export const SIDE_LABELS: Record<string, string> = {
  esquerdo: 'Esquerdo',
  direito: 'Direito',
  ambos: 'Ambos',
}

// As 4 perguntas OSTRC (0–3). `options[i]` = texto do nível i.
export interface OstrcQuestion {
  key: 'q_participation' | 'q_volume' | 'q_performance' | 'q_pain'
  label: string
  options: [string, string, string, string]
}

export const OSTRC_QUESTIONS: OstrcQuestion[] = [
  { key: 'q_participation', label: 'Participação nos treinos',
    options: ['Total, sem problema', 'Total, com problema', 'Reduzida', 'Não consigo'] },
  { key: 'q_volume', label: 'Redução no volume de treino',
    options: ['Nenhuma', 'Leve', 'Moderada', 'Muito / parei'] },
  { key: 'q_performance', label: 'Efeito no desempenho',
    options: ['Nenhum', 'Leve', 'Moderado', 'Muito afetado'] },
  { key: 'q_pain', label: 'Dor / sintomas',
    options: ['Nenhum', 'Leve', 'Moderado', 'Forte'] },
]

// Faixa de severidade (0–100) → rótulo + cor, só p/ exibição no histórico.
export function severityBand(sev: number): { label: string; tone: string } {
  if (sev >= 67) return { label: 'Alta', tone: 'text-red-400' }
  if (sev >= 34) return { label: 'Moderada', tone: 'text-amber-400' }
  if (sev > 0) return { label: 'Leve', tone: 'text-lime' }
  return { label: 'Sem sintomas', tone: 'text-text-secondary' }
}
