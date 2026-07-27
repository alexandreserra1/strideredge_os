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

# Cada exercício: id, name, phase, targets (fatores que corrige), when (pré|programa|pós), source,
# e `how` — COMO FAZER na prática, com um jeito de se auto-conferir. O `how` é instrução de execução
# (determinística, não passa pelo LLM): garante que o plano seja EXPLICATIVO de verdade, sem depender
# do humor do modelo. É técnica de execução (não alegação clínica), então herda a fonte do exercício.
EXERCISES = [
    {"id": "band_walk", "name": "Caminhada lateral com banda (glúteo médio)", "phase": "ativacao",
     "targets": ["pelvic_drop_deg", "knee_valgus_deg"], "when": "pre", "source": "PMC12372021",
     "how": "Banda elástica logo acima dos joelhos, meio agachado, pés paralelos. Dê passos "
            "pro lado sem deixar os joelhos caírem pra dentro. Você deve SENTIR ardência na "
            "lateral do quadril — é o sinal de que é o músculo certo. 2 séries de 10 passos "
            "pra cada lado."},
    {"id": "clamshell", "name": "Clam / concha com banda (rotadores e abdutores do quadril)",
     "phase": "ativacao", "targets": ["pelvic_drop_deg", "knee_valgus_deg"], "when": "pre",
     "source": "PMC12372021",
     "how": "Deitado de lado, joelhos dobrados e juntos. Abra o joelho de cima como uma concha, "
            "SEM rolar o quadril pra trás (o tronco fica parado). Sinta o glúteo trabalhar. "
            "2 séries de 15 pra cada lado."},
    {"id": "hip_abd_strength", "name": "Fortalecimento de abdutor de quadril (progressivo)",
     "phase": "forca", "targets": ["pelvic_drop_deg", "knee_valgus_deg", "asymmetry_pct"],
     "when": "programa", "source": "PMC3070501",
     "how": "Deitado de lado, perna de cima esticada. Suba ela devagar até uns 45° e desça com "
            "controle (2 segundos pra subir, 2 pra descer). Quando ficar fácil, adicione "
            "caneleira. 3 séries de 12 pra cada lado."},
    {"id": "single_leg_squat", "name": "Agachamento unipodal com controle do joelho",
     "phase": "forca", "targets": ["knee_valgus_deg", "asymmetry_pct"], "when": "programa",
     "source": "PMC3070501",
     "how": "Agache numa perna só, bem devagar. Olhe no espelho (ou se filme): o joelho NÃO "
            "pode cair pra dentro nem passar muito da ponta do pé. Vá só até onde consegue "
            "controlar. 3 séries de 8 pra cada lado."},
    {"id": "cadence_metronome", "name": "Reeducação de cadência com metrônomo (+5–10%)",
     "phase": "drill", "targets": ["cadence_spm", "knee_contact_deg"], "when": "programa",
     "source": "PMC10761631",
     "how": "Meça sua cadência agora: conte quantas vezes UM pé toca o chão em 20 segundos e "
            "multiplique por 6. Abra um app de metrônomo nesse número + 5% e corra fazendo a "
            "pisada bater junto com o bip. 1x na semana, 5 minutos, numa corrida leve."},
    {"id": "land_under_hip", "name": "Drill de aterrar o pé sob o quadril (menos passada longa)",
     "phase": "drill", "targets": ["knee_contact_deg", "cadence_spm"], "when": "programa",
     "source": "PMC9441414",
     "how": "Foque em aterrar o pé EMBAIXO do quadril, não lá na frente. Passos mais curtos e "
            "leves. Dica pra conferir: se você ouve o pé 'socando' o chão, ainda está pisando "
            "longe demais — encurte mais o passo."},
    {"id": "plyometrics", "name": "Pliometria reativa (saltos curtos, contato rápido)",
     "phase": "forca", "targets": ["vertical_oscillation_pct", "ground_contact_ms"],
     "when": "programa",
     "source": "Effects of Plyometric Jump Training on Running Economy in Endurance Runners",
     "how": "Saltinhos rápidos no lugar (ou pular corda), tocando o chão o MÍNIMO possível — "
            "pense 'chão quente, tira o pé rápido'. Aterrisse na base dos dedos, não no "
            "calcanhar. 3 séries de 20 toques. Comece leve."},
    {"id": "trunk_lean_cue", "name": "Ajuste de postura: leve inclinação do tronco a partir do tornozelo",
     "phase": "drill", "targets": ["trunk_lean_deg"], "when": "programa", "source": "PMC11135760",
     "how": "Incline o corpo INTEIRO levemente pra frente a partir do TORNOZELO (não dobre na "
            "cintura), como quem vai começar a cair pra frente e sai correndo. Você sente o "
            "peso indo pros dedos dos pés. Poucos graus bastam."},
]


def for_factors(factor_keys) -> list:
    """Exercícios que atacam pelo menos um dos fatores desviados. Determinístico + citado — o
    coach usa isso como fonte de verdade da prescrição."""
    keys = set(factor_keys)
    return [e for e in EXERCISES if keys & set(e["targets"])]
