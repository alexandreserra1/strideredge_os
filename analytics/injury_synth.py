"""analytics/injury_synth.py — gerador de exemplos SINTÉTICOS aterrado na literatura.

Por que existe: pra provar o PIPELINE de ML (treino → avaliação → predição → mesma interface do
`assess`) ANTES de ter outcomes reais (`injury_dataset.build_dataset`) ou um dataset rotulado de
licença permissiva. Cada exemplo é gerado a partir das FAIXAS IDEAIS citadas (`biomechanics.
ideal_targets`) + dos pesos de risco da literatura (`injury_risk.RISK_WEIGHT`):
  - saudável (label 0): fatores DENTRO do ideal.
  - lesionado (label 1): fatores DESVIADOS na direção de risco, com probabilidade proporcional
    ao peso do fator (queda pélvica/cadência desviam mais que tronco).

HONESTIDADE (não maquiar): isto NÃO é dado clínico. Um RF treinado aqui aprende a REGRA que
geramos — serve pra validar o encanamento (PR-AUC do fluxo, interface, serialização), NÃO a
validade preditiva. Rótulo: 'sintético/literatura'. Troca-se por dado real/permissivo sem mexer
na interface (é o ponto). Ver AI-STRATEGY.md.
"""

import random
from typing import Optional

from analytics.biomechanics import ideal_targets
from analytics.injury_risk import RISK_WEIGHT

FEATURE_ORDER = tuple(ideal_targets().keys())
_MAX_WEIGHT = max(RISK_WEIGHT.values())


def _sample_factor(spec: dict, weight: float, injured: bool, rng: random.Random) -> float:
    """Amostra um valor pro fator: dentro do ideal (saudável) ou desviado na direção de risco
    (lesionado, com chance proporcional ao peso do fator)."""
    lo, hi, direction = spec["lo"], spec["hi"], spec["dir"]
    span = hi - lo or 1.0
    if not injured or rng.random() > weight / _MAX_WEIGHT:
        # dentro do ideal (com leve ruído): saudável, ou fator não-desviado do lesionado
        return round(rng.uniform(lo, hi), 2)
    # desvio na direção de risco: acima do teto (lower_better/range) ou abaixo do piso (higher_better)
    if direction == "higher_better":
        return round(lo - rng.uniform(0.1, 0.6) * span, 2)
    return round(hi + rng.uniform(0.1, 0.6) * span, 2)


def generate(n: int = 400, injured_ratio: float = 0.3, seed: Optional[int] = 42) -> list:
    """Gera `n` exemplos rotulados `{features, label}` (label 1 = lesionado). `injured_ratio`
    mantém a classe positiva RARA de propósito (lesão é rara → força usar class_weight/PR-AUC)."""
    rng = random.Random(seed)
    targets = ideal_targets()
    out = []
    for _ in range(n):
        injured = rng.random() < injured_ratio
        features = {
            f: _sample_factor(targets[f], RISK_WEIGHT.get(f, 1.0), injured, rng)
            for f in FEATURE_ORDER
        }
        out.append({"features": features, "label": 1 if injured else 0})
    return out
