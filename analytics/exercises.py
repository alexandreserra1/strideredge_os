"""analytics/exercises.py — biblioteca ESTRUTURADA de exercícios corretivos (citada).

Hoje o FormCoach gera exercício 100% pelo LLM. O passo profissional é uma biblioteca
determinística: cada exercício amarrado aos FATORES biomecânicos que ele corrige (chaves de
`biomechanics.ideal_targets`), com a FASE (ativação/força/mobilidade/drill), o QUANDO (pré/pós/
programa) e a FONTE. Assim o "ajudar o atleta" (fortalecer, ativar, mobilizar) vira prescrição
citável — o LLM personaliza a entrega, não inventa o exercício.

Seed pequeno agora; cresce. Fontes são as MESMAS do corpus (rastreável). Base de evidência:
fortalecer abdutor de quadril reduz dor patelofemoral/banda IT (revisões de RCT).
"""

PHASES = ("ativacao", "forca", "mobilidade", "drill")   # ativação (pré), força (programa), etc.

# Cada exercício: id, name, phase, targets (fatores que corrige), when (pré|programa|pós), source.
EXERCISES = [
    {"id": "band_walk", "name": "Caminhada lateral com banda (glúteo médio)", "phase": "ativacao",
     "targets": ["pelvic_drop_deg", "knee_valgus_deg"], "when": "pre", "source": "PMC12372021"},
    {"id": "clamshell", "name": "Clam / concha com banda (rotadores e abdutores do quadril)",
     "phase": "ativacao", "targets": ["pelvic_drop_deg", "knee_valgus_deg"], "when": "pre",
     "source": "PMC12372021"},
    {"id": "hip_abd_strength", "name": "Fortalecimento de abdutor de quadril (progressivo)",
     "phase": "forca", "targets": ["pelvic_drop_deg", "knee_valgus_deg", "asymmetry_pct"],
     "when": "programa", "source": "PMC3070501"},
    {"id": "single_leg_squat", "name": "Agachamento unipodal com controle do joelho",
     "phase": "forca", "targets": ["knee_valgus_deg", "asymmetry_pct"], "when": "programa",
     "source": "PMC3070501"},
    {"id": "cadence_metronome", "name": "Reeducação de cadência com metrônomo (+5–10%)",
     "phase": "drill", "targets": ["cadence_spm", "knee_contact_deg"], "when": "programa",
     "source": "PMC10761631"},
    {"id": "land_under_hip", "name": "Drill de aterrar o pé sob o quadril (menos passada longa)",
     "phase": "drill", "targets": ["knee_contact_deg", "cadence_spm"], "when": "programa",
     "source": "PMC9441414"},
    {"id": "plyometrics", "name": "Pliometria reativa (saltos curtos, contato rápido)",
     "phase": "forca", "targets": ["vertical_oscillation_pct", "ground_contact_ms"],
     "when": "programa",
     "source": "Effects of Plyometric Jump Training on Running Economy in Endurance Runners"},
    {"id": "trunk_lean_cue", "name": "Ajuste de postura: leve inclinação do tronco a partir do tornozelo",
     "phase": "drill", "targets": ["trunk_lean_deg"], "when": "programa", "source": "PMC11135760"},
]


def for_factors(factor_keys) -> list:
    """Exercícios que atacam pelo menos um dos fatores desviados. Determinístico + citado — o
    coach usa isso como fonte de verdade da prescrição."""
    keys = set(factor_keys)
    return [e for e in EXERCISES if keys & set(e["targets"])]
