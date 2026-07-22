"""analytics/injury_model.py — modelo de risco TREINADO (Random Forest), o upgrade do prior.

Mesma INTERFACE do `injury_risk.assess` (risk_band + factors citados + caveat) — é drop-in: o
`prior` da literatura e o `treinado` produzem a MESMA forma, então quem consome (form_coach) não
muda quando trocamos. O que muda: a FAIXA vem da probabilidade do RF (não do score aditivo), e o
peso de cada fator vem do `feature_importances_` do modelo (não da tabela ordinal).

Rigor (AI-STRATEGY): `class_weight='balanced'` (lesão é rara — não SMOTE, que distorce calibração),
avaliação por **PR-AUC** (não acurácia), validação **subject-wise** quando há `user_id` (vídeos do
mesmo atleta no MESMO fold, senão vaza). Hoje treina em sintético (`injury_synth`) pra provar o
fluxo; troca por `injury_dataset.build_dataset` (dado real) sem mexer na interface.
"""

from typing import Optional

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold, GroupKFold

from analytics.biomechanics import ideal_targets, diagnose
from analytics.injury_risk import _by_injury
from analytics.injury_synth import FEATURE_ORDER
from analytics.injury_quality import clean


def _band(prob: float) -> str:
    """Faixa RELATIVA a partir da probabilidade do RF (não é probabilidade calibrada de lesão)."""
    if prob < 0.15:
        return "baixo"
    if prob < 0.35:
        return "moderado"
    if prob < 0.6:
        return "elevado"
    return "alto"


def _vectorize(features: dict, targets: dict) -> list:
    """Dict de fatores → vetor ordenado (FEATURE_ORDER). Fator ausente = meio da faixa ideal
    (neutro: uma vista lateral não mede queda pélvica → não deve empurrar o risco pra nenhum lado)."""
    row = []
    for f in FEATURE_ORDER:
        val = features.get(f)
        if val is None:
            spec = targets[f]
            val = (spec["lo"] + spec["hi"]) / 2
        row.append(val)
    return row


class RiskModel:
    """Random Forest de risco de lesão. Composição: recebe os exemplos no `train`, serve no
    `predict` com a mesma forma do prior da literatura."""

    def __init__(self, n_estimators: int = 200, seed: int = 42):
        self._rf = RandomForestClassifier(
            n_estimators=n_estimators, class_weight="balanced", random_state=seed)
        self._targets = ideal_targets()
        self.trained = False

    def train(self, dataset: list) -> dict:
        """Treina no dataset `[{features, label}]`. Filtra dado ruidoso ANTES (nenhum valor
        impossível/duplicata treina). Devolve o boletim (PR-AUC + relatório de limpeza)."""
        dataset, quality = clean(dataset)   # §7: dado validado, nunca chutado
        x = np.array([_vectorize(e["features"], self._targets) for e in dataset])
        y = np.array([e["label"] for e in dataset])
        groups = [e.get("user_id") for e in dataset]
        report = self._evaluate(x, y, groups)
        self._rf.fit(x, y)
        self.trained = True
        return {**report, "quality": quality}

    def _evaluate(self, x, y, groups) -> dict:
        """PR-AUC por validação cruzada. Subject-wise (GroupKFold) quando há user_id em todos —
        senão estratificada (sintético não tem atleta). Honesto sobre qual rodou."""
        subject_wise = all(g is not None for g in groups) and len(set(groups)) >= 5
        splitter = (GroupKFold(n_splits=5) if subject_wise
                    else StratifiedKFold(n_splits=5, shuffle=True, random_state=42))
        scores = []
        split = splitter.split(x, y, groups) if subject_wise else splitter.split(x, y)
        for tr, te in split:
            if len(set(y[tr])) < 2:
                continue
            rf = RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=0)
            rf.fit(x[tr], y[tr])
            scores.append(average_precision_score(y[te], rf.predict_proba(x[te])[:, 1]))
        return {
            "pr_auc": round(float(np.mean(scores)), 3) if scores else None,
            "validation": "subject-wise" if subject_wise else "stratified",
            "n": int(len(y)), "positives": int(y.sum()),
        }

    def predict(self, metrics: dict, profile: Optional[dict] = None,
                history: Optional[dict] = None) -> dict:
        """Risco do atleta — MESMA forma do `assess` (drop-in). Faixa da probabilidade do RF;
        fatores explicados/citados via `diagnose`; peso via importância do modelo."""
        if not self.trained:
            raise RuntimeError("modelo não treinado — chame train() antes de predict()")
        targets = ideal_targets(profile, history)
        prob = float(self._rf.predict_proba([_vectorize(metrics, targets)])[0][1])
        importances = dict(zip(FEATURE_ORDER, self._rf.feature_importances_))

        sensitized = set((history or {}).get("factors", []))   # mesma forma do prior (interface)
        devs = diagnose(metrics, targets)
        factors = []
        for d in devs:
            weight = round(float(importances.get(d["metric"], 0.0)), 3)
            factors.append({
                "metric": d["metric"], "label": d["label"], "value": d["value"],
                "unit": d["unit"], "side": d["side"], "source": d["source"],
                "plain": d["plain"], "weight": weight,
                "sensitized": d["metric"] in sensitized,
                "contribution": round(d["severity"] * weight, 3),
            })
        factors.sort(key=lambda f: f["contribution"], reverse=True)
        # Decomposição por-lesão: mesmo contrato do prior (aditivo). Reusa o helper aterrado na
        # taxonomia (severity×RISK_WEIGHT) — a mesma regra de "não avaliável" vale aqui.
        by_injury = _by_injury(metrics, {d["metric"]: d for d in devs}, sensitized)

        return {
            "risk_band": _band(prob), "score": round(prob, 3), "factors": factors,
            "by_injury": by_injury,
            "model": "treinado",
            "caveat": "Modelo TREINADO (Random Forest). Hoje sobre dados sintéticos aterrados na "
                      "literatura — prova o fluxo, não a validade preditiva; recalibra com outcomes "
                      "reais. Faixa RELATIVA, não probabilidade de lesão nem diagnóstico.",
        }
