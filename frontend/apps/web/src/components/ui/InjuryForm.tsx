import { useMemo, useState } from 'react'
import type { InjuryTaxonomy } from '@strideredge/core'
import type { InjuryLogInput } from '@strideredge/core'
import RatingSegments from './RatingSegments'
import { REGION_LABELS, SIDE_LABELS, OSTRC_QUESTIONS } from './injuryCopy'

interface InjuryFormProps {
  taxonomy: InjuryTaxonomy
  onSubmit: (report: InjuryLogInput) => Promise<void>
  saving: boolean
}

const TODAY = new Date().toISOString().slice(0, 10)

// Form do log OSTRC. Cascata região→diagnóstico→lado→data→4 perguntas. `diagnosis` é OBRIGATÓRIO
// no cliente (o backend aceita null de propósito; a trava real do dataset é no consumidor).
export default function InjuryForm({ taxonomy, onSubmit, saving }: InjuryFormProps) {
  const [region, setRegion] = useState('')
  const [diagnosis, setDiagnosis] = useState('')
  const [side, setSide] = useState('')
  const [onsetDate, setOnsetDate] = useState('')
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [notes, setNotes] = useState('')

  const dxOptions = useMemo(
    () => taxonomy.diagnoses.filter((d) => !region || d.region === region),
    [taxonomy.diagnoses, region],
  )
  const selectedDx = taxonomy.diagnoses.find((d) => d.id === diagnosis)
  const canSubmit = !!diagnosis && !!onsetDate && !saving

  const onRegionChange = (r: string) => {
    setRegion(r)
    setDiagnosis('')   // troca de região invalida o diagnóstico
  }

  const submit = async () => {
    if (!canSubmit) return
    await onSubmit({
      region: region || selectedDx?.region || null,
      diagnosis, side: side || null, onset_date: onsetDate,
      notes: notes.trim() || null, ...answers,
    })
    setRegion(''); setDiagnosis(''); setSide(''); setOnsetDate(''); setAnswers({}); setNotes('')
  }

  return (
    <div className="space-y-5 rounded-2xl border border-border-light bg-surface-100 p-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-1.5">
          <span className="text-sm font-medium">Região</span>
          <select value={region} onChange={(e) => onRegionChange(e.target.value)} className="input-base w-full">
            <option value="">Todas</option>
            {taxonomy.regions.map((r) => <option key={r} value={r}>{REGION_LABELS[r] ?? r}</option>)}
          </select>
        </label>
        <label className="space-y-1.5">
          <span className="text-sm font-medium">Diagnóstico <span className="text-red-400">*</span></span>
          <select value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} className="input-base w-full">
            <option value="">Selecione…</option>
            {dxOptions.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
          </select>
        </label>
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

      <div className="space-y-4 border-t border-border-light pt-4">
        <p className="text-xs text-text-secondary">Nas últimas semanas, por causa desta lesão:</p>
        {OSTRC_QUESTIONS.map((q) => (
          <RatingSegments key={q.key} label={q.label} options={q.options}
            value={answers[q.key] ?? null}
            onChange={(v) => setAnswers((a) => ({ ...a, [q.key]: v }))} />
        ))}
      </div>

      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
        placeholder="Notas (opcional)" className="input-base w-full resize-none" />

      <button onClick={submit} disabled={!canSubmit} className="btn-primary w-full">
        {saving ? 'Salvando…' : 'Registrar lesão'}
      </button>
    </div>
  )
}
