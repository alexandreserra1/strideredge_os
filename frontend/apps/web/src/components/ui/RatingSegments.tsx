interface RatingSegmentsProps {
  label: string
  value: number | null
  onChange: (v: number) => void
  // Texto de cada nível (índice = valor). Ex.: ['Sem problema', 'Leve', 'Moderado', 'Grave']
  options: string[]
}

// Segmented control p/ escala OSTRC 0–3: pills lado a lado, padrão mobile p/ Likert curto.
// Acessível: radiogroup + aria-checked (estado não depende só de cor).
export default function RatingSegments({ label, value, onChange, options }: RatingSegmentsProps) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium text-text-primary">{label}</legend>
      <div role="radiogroup" aria-label={label} className="grid grid-cols-4 gap-1.5">
        {options.map((opt, i) => {
          const active = value === i
          return (
            <button
              key={i}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(i)}
              className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded-xl border text-center transition-all duration-200
                ${active
                  ? 'bg-lime/10 text-lime border-lime/30'
                  : 'text-text-secondary border-border-light hover:text-text-primary hover:bg-white/5'
                }`}
            >
              <span className="text-base font-bold leading-none">{i}</span>
              <span className="text-[10px] leading-tight">{opt}</span>
            </button>
          )
        })}
      </div>
    </fieldset>
  )
}
