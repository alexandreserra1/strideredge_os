import { useCallback, useEffect, useState } from 'react'
import { api } from '@strideredge/core'
import type { InjuryLogInput } from '@strideredge/core'
import type { InjuryReport, InjuryTaxonomy } from '@strideredge/core'
import InjuryForm from '../components/ui/InjuryForm'
import InjuryList from '../components/ui/InjuryList'

// Tela "Minhas lesões" — rota irmã da análise, fora do fluxo de upload. Log OSTRC append-only:
// fonte principal do dataset do modelo de risco treinado.
export default function MyInjuries() {
  const [taxonomy, setTaxonomy] = useState<InjuryTaxonomy | null>(null)
  const [reports, setReports] = useState<InjuryReport[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const loadReports = useCallback(() => {
    api.injuries.list().then(setReports).catch(() => setError('Não foi possível carregar suas lesões.'))
  }, [])

  useEffect(() => {
    api.injuries.taxonomy().then(setTaxonomy).catch(() => setError('Não foi possível carregar o vocabulário.'))
    loadReports()
  }, [loadReports])

  const onSubmit = useCallback(async (report: InjuryLogInput) => {
    setSaving(true)
    setError('')
    try {
      await api.injuries.log(report)
      loadReports()
    } catch {
      setError('Não foi possível registrar. Revise os campos e tente de novo.')
    } finally {
      setSaving(false)
    }
  }, [loadReports])

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Minhas lesões</h1>
        <p className="text-sm text-text-secondary">
          Registre lesões e sintomas ao longo do tempo. Isso aterra a análise de risco no seu histórico real.
        </p>
      </header>

      {error && (
        <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400">{error}</p>
      )}

      {taxonomy && <InjuryForm taxonomy={taxonomy} onSubmit={onSubmit} saving={saving} />}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-text-secondary">Histórico</h2>
        <InjuryList reports={reports} taxonomy={taxonomy} />
      </section>
    </div>
  )
}
