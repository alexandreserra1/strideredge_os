import { Info } from 'lucide-react'

/** Ícone (i) com popover explicativo no hover. Fica ao lado do TÍTULO de um card —
 * não conflita com o hover do gráfico (que dispara na área de plotagem). */
export default function InfoHint({ text }: { text: string }) {
  return (
    <span className="relative inline-flex group align-middle">
      <Info size={13} className="text-text-muted hover:text-text-secondary transition-colors cursor-help" />
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 w-56 -translate-x-1/2
          glass rounded-xl border border-border-light p-3 text-[11px] font-normal normal-case tracking-normal
          leading-snug text-text-secondary opacity-0 shadow-xl transition-opacity duration-150
          group-hover:opacity-100"
      >
        {text}
      </span>
    </span>
  )
}
