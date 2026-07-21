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


# ganho da relação MECÂNICA (não é número publicado): quanto cada fator ligado à cadência se
# desloca por spm ABAIXO do piso ideal. Cadência baixa = passada longa → o pé aterra à frente do
# quadril, o que ALONGA o tempo de contato (menos "mola") e deixa o joelho mais ESTENDIDO no apoio
# (overstriding). É acoplamento cinemático conhecido (cadência↔GCT↔passada), com ruído por cima.
_CADENCE_COUPLING = {
    "ground_contact_ms": 3.0,   # ~3 ms de contato a mais por spm abaixo do ideal
    "knee_contact_deg": 0.8,    # joelho ~0.8° mais estendido no apoio por spm abaixo do ideal
}


def _apply_cadence_coupling(features: dict, targets: dict, rng: random.Random) -> None:
    """Desloca GCT e joelho na direção de RISCO proporcional a quão abaixo do piso ideal a cadência
    ficou (relação mecânica, não distribuição publicada). Ruído mantém sobreposição; clamp mantém o
    valor dentro da faixa plausível do fator. Muta `features` in place."""
    deficit = max(0.0, targets["cadence_spm"]["lo"] - features["cadence_spm"])   # spm abaixo do ideal
    if deficit <= 0:
        return
    for factor, gain in _CADENCE_COUPLING.items():
        t = targets[factor]
        shifted = features[factor] + gain * deficit + rng.gauss(0, gain * 2)
        features[factor] = round(min(max(shifted, t["lo"]), t["hi"]), 2)


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
        _apply_cadence_coupling(features, targets, rng)   # acopla GCT/joelho à cadência
        diagnosis = rng.choices(dx_ids, weights=dx_weights, k=1)[0] if injured else None
        out.append({"features": features, "label": 1 if injured else 0, "diagnosis": diagnosis})
    return out
