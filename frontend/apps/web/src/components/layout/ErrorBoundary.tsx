import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

interface Props {
  children: ReactNode
  /** rótulo opcional pra distinguir qual área quebrou (log/diagnóstico) */
  label?: string
}
interface State {
  hasError: boolean
}

/**
 * Defesa em profundidade: se qualquer render lançar (ex.: um campo esperado da API vier
 * `undefined` e alguém fizer `.map`/`.length`), o React normalmente desmonta a árvore INTEIRA e
 * deixa a tela preta. Esse boundary captura o erro, isola a área afetada e mostra um fallback
 * amigável em vez de derrubar o app. Envolvemos por-rota pra que um erro numa tela não mate a
 * navegação inteira.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Log no console pra diagnóstico; nada de tela preta silenciosa.
    console.error(`[ErrorBoundary${this.props.label ? ' ' + this.props.label : ''}]`, error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="max-w-md mx-auto my-10 rounded-xl border border-accent-red/25 bg-accent-red/5 p-6 text-center">
          <AlertTriangle size={24} className="mx-auto text-accent-red mb-3" />
          <p className="text-sm font-semibold">Algo quebrou ao mostrar isto.</p>
          <p className="text-xs text-text-secondary mt-1">Recarregue a página para continuar.</p>
          <button onClick={() => window.location.reload()} className="btn-primary text-sm mt-4">
            Recarregar a página
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
