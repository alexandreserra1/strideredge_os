import { Info } from 'lucide-react'
import * as Tooltip from '@radix-ui/react-tooltip'

/** Ícone (i) com tooltip explicativo — agora via Radix (acessível: teclado, foco, ARIA,
 * posicionamento sem clipping). Mesma API de antes: só passa `text`. O Provider fica na raiz
 * do app (App.tsx). */
export default function InfoHint({ text }: { text: string }) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button type="button" aria-label="Mais informação"
          className="inline-flex align-middle text-text-muted hover:text-text-secondary transition-colors cursor-help focus:outline-none focus-visible:text-text-secondary">
          <Info size={13} />
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content sideOffset={6} collisionPadding={8}
          className="z-[60] max-w-[15rem] glass rounded-xl border border-border-light p-3 text-[11px]
            font-normal normal-case tracking-normal leading-snug text-text-secondary shadow-xl
            data-[state=delayed-open]:animate-fade-in">
          {text}
          <Tooltip.Arrow className="fill-[var(--surface-100)]" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}
