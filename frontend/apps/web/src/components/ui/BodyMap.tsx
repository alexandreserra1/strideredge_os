import Model, { type IExerciseData, type Muscle, type IMuscleStats } from 'react-body-highlighter'
import { REGION_LABELS } from './injuryCopy'

interface BodyMapProps {
  selected: string[]
  onToggle: (region: string) => void
}

const REGION_ORDER = ['quadril', 'coxa', 'joelho_frente', 'joelho_lateral', 'canela', 'tornozelo', 'pe']

// Nossa taxonomia é por ARTICULAÇÃO/local; a ilustração é por MÚSCULO. Mapeamos onde há equivalente
// anatômico (o corpo acende o músculo). Tornozelo e pé não são músculos → selecionáveis só pelo chip.
const REGION_TO_MUSCLE: Record<string, Muscle> = {
  quadril: 'abductors', coxa: 'quadriceps',
  joelho_frente: 'knees', joelho_lateral: 'knees', canela: 'calves',
}
const MUSCLE_TO_REGION: Partial<Record<Muscle, string>> = {
  abductors: 'quadril', quadriceps: 'coxa', knees: 'joelho_frente', calves: 'canela',
}

// Ilustração muscular anatômica (react-body-highlighter, MIT) como o desenho; cliques mapeados às
// nossas regiões. Os chips embaixo garantem as 7 regiões (mesmo as que não têm músculo).
export default function BodyMap({ selected, onToggle }: BodyMapProps) {
  const muscles = [...new Set(selected.map((r) => REGION_TO_MUSCLE[r]).filter(Boolean))] as Muscle[]
  const data: IExerciseData[] = muscles.length ? [{ name: 'selecionadas', muscles }] : []

  const onMuscleClick = ({ muscle }: IMuscleStats) => {
    const region = MUSCLE_TO_REGION[muscle]
    if (region) onToggle(region)
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <Model type="anterior" style={{ width: '13rem' }} data={data}
        bodyColor="#3f3f46" highlightedColors={['#a3e635']} onClick={onMuscleClick} />
      <div className="flex flex-wrap justify-center gap-1.5">
        {REGION_ORDER.map((region) => {
          const active = selected.includes(region)
          return (
            <button key={region} type="button" onClick={() => onToggle(region)}
              className={`rounded-full border px-3 py-1 text-xs transition-all
                ${active ? 'bg-lime/10 text-lime border-lime/30'
                         : 'text-text-secondary border-border-light hover:text-text-primary'}`}>
              {REGION_LABELS[region]}
            </button>
          )
        })}
      </div>
    </div>
  )
}
