"""analytics/injury_synth.py — gerador de exemplos SINTÉTICOS parametrizado pela literatura.

Aterrado em estatística REAL publicada (`injury_literature.LIT_PARAMS`): fator DISCRIMINANTE é
amostrado da distribuição (média±DP) do seu grupo (saudável vs lesionado) — a sobreposição real
pelos DPs dá ao RF um sinal honesto (AUC ~0.8, não 1.0). Fator SEM split publicado sai da faixa
ideal p/ os dois grupos (não fabricamos discriminação). Tipo de lesão amostrado pela frequência
real da coorte N=1.798.

HONESTIDADE: continua sendo simulação (não dado individual real) — serve pra aterrar o prior e
provar o pipeline com sobreposição realista. Troca por dado real (`build_dataset`) ou dataset
externo permissivo sem mexer na interface. Ver `injury_literature.py` e AI-STRATEGY.md.
"""

import random
from typing import Optional

from analytics.biomechanics import ideal_targets
from analytics.injury_literature import LIT_PARAMS, injury_type_weights

FEATURE_ORDER = tuple(ideal_targets().keys())


def _sample_factor(factor: str, spec: dict, injured: bool, rng: random.Random) -> float:
    """Discriminante → Normal(média, DP) do grupo (real, publicado). Não-discriminante → faixa
    ideal p/ os dois grupos (sem discriminação fabricada)."""
    lit = LIT_PARAMS.get(factor)
    if lit:
        mean, sd = lit["injured"] if injured else lit["healthy"]
        return round(rng.gauss(mean, sd), 2)
    return round(rng.uniform(spec["lo"], spec["hi"]), 2)


def generate(n: int = 400, injured_ratio: float = 0.3, seed: Optional[int] = 42) -> list:
    """Gera `n` exemplos rotulados `{features, label, diagnosis}` (label 1 = lesionado). O tipo de
    lesão (`diagnosis`) do lesionado vem da frequência real; `injured_ratio` mantém a classe rara."""
    rng = random.Random(seed)
    targets = ideal_targets()
    dx_ids, dx_weights = injury_type_weights()
    out = []
    for _ in range(n):
        injured = rng.random() < injured_ratio
        features = {f: _sample_factor(f, targets[f], injured, rng) for f in FEATURE_ORDER}
        diagnosis = rng.choices(dx_ids, weights=dx_weights, k=1)[0] if injured else None
        out.append({"features": features, "label": 1 if injured else 0, "diagnosis": diagnosis})
    return out
