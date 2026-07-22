"""analytics/injury_bayes.py — risco com PRIOR informativo que ATUALIZA online (alavancagem #4-B).

A ponte HONESTA entre o prior da literatura (`injury_risk.assess`) e o RF treinado
(`injury_model.RiskModel`). Começa IDÊNTICO ao score citado (médias posteriores = `RISK_WEIGHT`);
cada outcome REAL desloca os pesos por uma atualização bayesiana — regressão logística online por
aproximação de densidade assumida (Chapelle & Li, 2011: posterior diagonal gaussiano, média `m` +
precisão `λ` por peso, atualizado exemplo a exemplo).

Por que ISTO e não um RF agora: o RF precisa de dezenas de casos rotulados pra treinar honesto
(abaixo disso, overfit). O prior bayesiano funciona com POUCOS casos — com N=0 é o prior da
literatura (não regride), e cada lesão logada já ajusta o modelo. Faz a coleta render desde o 1º
atleta, sem o dia-zero circular de treinar em sintético. Mesma interface do `assess` (drop-in);
`predict` ainda expõe `uncertainty` (quantos casos reais informaram + desvio-padrão do score).
Ver AI-STRATEGY.md § "#4 — alternativas".
"""

import math
from typing import Optional

from analytics.biomechanics import ideal_targets, diagnose
from analytics.injury_risk import RISK_WEIGHT, build_risk

# λ inicial de cada peso = confiança no prior da literatura. Alto = precisa de MAIS casos reais pra
# mover o peso do valor citado (regularização informativa). Ordinal, calibrável com dado.
_PRIOR_PRECISION = 6.0
# Intercepto (base-rate): lesão é rara, então o link logístico parte de probabilidade baixa. Só
# serve à MATEMÁTICA do update — não entra no score aditivo reportado (que é Σ severidade×peso).
_INTERCEPT_MEAN = -4.0
_INTERCEPT_PRECISION = 1.0

_CAVEAT = (
    "Prior da literatura REFINADO online por outcomes reais (regressão logística bayesiana). Com "
    "zero caso real é idêntico ao score citado; cada lesão logada ajusta os pesos. Faixa RELATIVA, "
    "não probabilidade nem diagnóstico. Veja `uncertainty.n_real_updates` — quantos casos o informaram.")


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


class BayesianRiskModel:
    """Peso de risco por fator como uma CRENÇA (média posterior) que a evidência real atualiza.

    Composição, não herança: reusa `diagnose` (severidades = features) e `build_risk` (monta a
    saída com pesos injetáveis) do módulo do prior. `partial_fit` folds outcomes reais; `predict`
    tem a MESMA forma do `assess` + um bloco `uncertainty`."""

    FACTORS = tuple(RISK_WEIGHT.keys())

    def __init__(self, prior_precision: float = _PRIOR_PRECISION):
        self._m = dict(RISK_WEIGHT)                              # médias começam no prior citado
        self._lambda = {f: prior_precision for f in self.FACTORS}
        self._m0, self._lambda0 = _INTERCEPT_MEAN, _INTERCEPT_PRECISION
        self._targets = ideal_targets()
        self.n_updates = 0

    def _features(self, metrics: dict) -> dict:
        """Severidade por fator (0 se dentro do ideal OU não medido) — MESMO espaço que o `assess`
        usa pra pontuar, então o que o modelo aprende casa com o que ele pontua."""
        dev = {d["metric"]: d for d in diagnose(metrics, self._targets)}
        return {f: (dev[f]["severity"] if f in dev else 0.0) for f in self.FACTORS}

    def partial_fit(self, examples: list) -> "BayesianRiskModel":
        """Atualiza o posterior com exemplos rotulados reais `[{features, label}]` — online (ADF).
        Chamável em lote (recoleta o dataset real) ou 1 a 1 (streaming). Idempotente por natureza:
        mais evidência aperta a precisão, então updates tardios movem menos que os primeiros."""
        for e in examples:
            x = self._features(e["features"])
            y = float(e["label"])
            z = self._m0 + sum(self._m[f] * x[f] for f in self.FACTORS)
            p = _sigmoid(z)
            g = p * (1.0 - p)                                    # variância de Bernoulli (curvatura)
            self._lambda0 += g                                  # intercepto (base-rate)
            self._m0 += (y - p) / self._lambda0
            for f in self.FACTORS:
                xi = x[f]
                if xi == 0.0:
                    continue                                    # fator não desviado não informa este caso
                self._lambda[f] += xi * xi * g                  # precisão sobe → passos futuros menores
                self._m[f] += xi * (y - p) / self._lambda[f]    # média puxada na direção do erro
            self.n_updates += 1
        return self

    def _weights(self) -> dict:
        """Pesos de pontuação = médias posteriores, com PISO 0: num app de prevenção não deixamos um
        fator de risco VIRAR protetor (peso negativo) sem evidência forte — a crença interna pode
        cair, mas o score não inverte por ruído."""
        return {f: max(0.0, round(self._m[f], 3)) for f in self.FACTORS}

    def predict(self, metrics: dict, profile: Optional[dict] = None,
                history: Optional[dict] = None) -> dict:
        """Risco do atleta — MESMA forma do `assess` (drop-in), com os pesos posteriores + um bloco
        `uncertainty` (honestidade: com poucos casos, o desvio-padrão do score é grande)."""
        out = build_risk(metrics, profile, history, self._weights(), "prior-bayes", _CAVEAT)
        out["uncertainty"] = self._uncertainty(metrics)
        return out

    def _uncertainty(self, metrics: dict) -> dict:
        """Quão firme é este score. `score_std` = √Σ(severidade²/λ) — cai conforme a evidência real
        aperta as precisões. `n_real_updates`=0 → é o prior puro (incerteza só do prior)."""
        x = self._features(metrics)
        var = sum((x[f] ** 2) / self._lambda[f] for f in self.FACTORS)
        return {"n_real_updates": self.n_updates, "score_std": round(math.sqrt(var), 3)}
