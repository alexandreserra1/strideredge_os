import { useState } from 'react'
import type { InjuryTaxonomy, InjuryLogInput } from '@strideredge/core'
import BodyMap from './BodyMap'
import RatingSegments from './RatingSegments'
import { REGION_LABELS, SIDE_LABELS, OSTRC_QUESTIONS } from './injuryCopy'

interface InjuryFormProps {
  taxonomy: InjuryTaxonomy
  onSubmit: (reports: InjuryLogInput[]) => Promise<void>
  saving: boolean
}

const TODAY = new Date().toISOString().slice(0, 10)
type RegionEntry = { answers: Record<string, number>; symptom: string }
const emptyEntry = (): RegionEntry => ({ answers: {}, symptom: '' })

// Reframe: o atleta marca ONDE dói no mapa (região = verdade estruturada), não auto-diagnostica.
// Cada região marcada tem seu próprio OSTRC (append-only: vira uma linha por região). O texto livre
// descreve o sintoma/laudo — vira contexto do coach e candidato a rótulo via LLM em coach-time.
export default function InjuryForm({ taxonomy, onSubmit, saving }: InjuryFormProps) {
  const [regions, setRegions] = useState<string[]>([])
  const [side, setSide] = useState('')
  const [onsetDate, setOnsetDate] = useState('')
  const [notes, setNotes] = useState('')
  const [entries, setEntries] = useState<Record<string, RegionEntry>>({})

  const canSubmit = regions.length > 0 && !!onsetDate && !saving

  const toggleRegion = (r: string) => {
    setRegions((prev) => prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r])
    setEntries((prev) => prev[r] ? prev : { ...prev, [r]: emptyEntry() })
  }
  const patch = (r: string, e: Partial<RegionEntry>) =>
    setEntries((prev) => ({ ...prev, [r]: { ...prev[r], ...e } }))
  const copyPrev = (r: string, prevR: string) => patch(r, { answers: { ...entries[prevR].answers } })

  const submit = async () => {
    if (!canSubmit) return
    const reports: InjuryLogInput[] = regions.map((r) => ({
      region: r, side: side || null, onset_date: onsetDate,
      symptom_text: entries[r]?.symptom.trim() || null,
      notes: notes.trim() || null, ...entries[r]?.answers,
    }))
    await onSubmit(reports)
    setRegions([]); setSide(''); setOnsetDate(''); setNotes(''); setEntries({})
  }

  return (
    <div className="space-y-5 rounded-2xl border border-border-light bg-surface-100 p-5">
      <div className="space-y-1.5">
        <p className="text-sm font-medium">Onde dói? <span className="text-red-400">*</span></p>
        <p className="text-xs text-text-secondary">Toque em um ou mais pontos. Não precisa saber o nome da lesão.</p>
        <BodyMap selected={regions} onToggle={toggleRegion} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-1.5">
          <span className="text-sm font-medium">Lado</span>
          <select value={side} onChange={(e) => setSide(e.target.value)} className="input-base w-full">
            <option value="">Não especificado</option>
            {taxonomy.sides.map((s) => <option key={s} value={s}>{SIDE_LABELS[s] ?? s}</option>)}
          </select>
        </label>
        <label className="space-y-1.5">
          <span className="text-sm font-medium">Início <span className="text-red-400">*</span></span>
          <input type="date" max={TODAY} value={onsetDate}
            onChange={(e) => setOnsetDate(e.target.value)} className="input-base w-full" />
        </label>
      </div>

      {regions.map((r, i) => (
        <div key={r} className="space-y-4 rounded-xl border border-border-light p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-lime">{REGION_LABELS[r] ?? r}</p>
            {i > 0 && (
              <button type="button" onClick={() => copyPrev(r, regions[i - 1])}
                className="text-xs text-text-secondary hover:text-text-primary underline">
                copiar respostas do anterior
              </button>
            )}
          </div>
          <p className="text-xs text-text-secondary">Nas últimas semanas, por causa desta lesão:</p>
          {OSTRC_QUESTIONS.map((q) => (
            <RatingSegments key={q.key} label={q.label} options={q.options}
              value={entries[r]?.answers[q.key] ?? null}
              onChange={(v) => patch(r, { answers: { ...entries[r]?.answers, [q.key]: v } })} />
          ))}
          <textarea value={entries[r]?.symptom ?? ''} onChange={(e) => patch(r, { symptom: e.target.value })}
            rows={2} placeholder="Descreva o que sente, ou o diagnóstico se um médico te deu (opcional)"
            className="input-base w-full resize-none" />
        </div>
      ))}

      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
        placeholder="Notas gerais (opcional)" className="input-base w-full resize-none" />

      <button onClick={submit} disabled={!canSubmit} className="btn-primary w-full">
        {saving ? 'Salvando…' : `Registrar ${regions.length > 1 ? `${regions.length} lesões` : 'lesão'}`}
      </button>
    </div>
  )
}
