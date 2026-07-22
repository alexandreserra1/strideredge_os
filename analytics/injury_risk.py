"""analytics/injury_risk.py — modelo de risco de lesão TRANSPARENTE, aterrado na literatura.

Por que NÃO é um random forest (ainda): treinar um classificador supervisionado exige
OUTCOMES rotulados — atletas acompanhados no tempo, com lesão registrada. Não temos esse
dado. O honesto com o que temos (tamanhos de efeito publicados, não dado bruto) é uma
**regressão logística / score aditivo** cujos PESOS vêm da força de associação de cada fator
biomecânico com lesão — cada peso citando o estudo (via a fonte do alvo em biomechanics).

Saída = **FAIXA de risco RELATIVA** (baixo/moderado/elevado/alto), NUNCA "X% de chance": um
score de log-odds não calibrado não pode prometer probabilidade. É explicável (mostra os
fatores que puxaram o risco), auditável (cada fator cita a fonte) e é o `prior` que um modelo
TREINADO (XGBoost, com class weights + calibração + validação subject-wise) recalibra quando
houver outcomes reais. Ver AI-STRATEGY.md.

Design: REUSA `diagnose` (biomechanics) — que já dá o desvio de cada métrica (severity = quão
longe do ideal, normalizado; + source + plain + label). Aqui só pesamos por risco e agregamos.
"""

from typing import Optional

from analytics.biomechanics import ideal_targets, diagnose
from analytics.injury_taxonomy import DIAGNOSES


# Peso de RISCO por fator = quão forte a literatura liga o desvio a LESÃO (não a performance).
# Ordinal de propósito (3=forte, 2=moderado, 1=leitura) — seria FALSO cravar um odds ratio
# exato pra cada um sem o estudo na mão. Os mais fortes: cadência baixa (6-7x risco tibial) e os
# sinais do plano frontal (queda pélvica / valgo → dor patelofemoral, banda IT). A FONTE de cada
# um é a mesma do alvo em biomechanics.ideal_targets (rastreável).
RISK_WEIGHT = {
    "cadence_spm": 3.0,              # < ~166 spm: 6-7x risco de lesão tibial
    "pelvic_drop_deg": 3.0,         # queda pélvica → PFP / banda IT
    "knee_valgus_deg": 3.0,         # valgo dinâmico → dor patelofemoral
    "knee_contact_deg": 2.0,        # overstriding (joelho reto no apoio) → impacto direto
    "vertical_oscillation_pct": 2.0,
    "asymmetry_pct": 2.0,           # assimetria → lesão unilateral
    "ground_contact_ms": 1.0,
    "trunk_lean_deg": 1.0,
}


# Multiplicador de risco p/ fator ligado a lesão PRÉVIA do atleta (histórico = preditor #1).
# Moderado de propósito (não dobra): sinaliza sem dominar o score da forma atual.
SENSITIZE = 1.5


# Fatores que SÓ o vídeo de FRENTE mede (plano frontal). No vídeo lateral saem None — logo um
# diagnóstico frontal (pfp/itbs) fica "não avaliável" numa captura de lado, NUNCA "risco baixo".
_FRONTAL_FACTORS = {"pelvic_drop_deg", "knee_valgus_deg"}


def _injury_contrib(factors: list, dev_by_metric: dict, sensitized: set) -> tuple:
    """Contribuição de risco de UM diagnóstico = Σ (severity × peso_de_risco) só dos SEUS fatores
    DESVIADOS. Reusa exatamente a `severity` de `diagnose` e os pesos `RISK_WEIGHT` — mesma
    lógica/mesmos pesos do score agregado, sem inventar nada novo."""
    total, drivers = 0.0, []
    for f in factors:
        d = dev_by_metric.get(f)      # None = medido e dentro do ideal (não contribui)
        if not d:
            continue
        weight = RISK_WEIGHT.get(f, 1.0)
        c = round(d["severity"] * weight * (SENSITIZE if f in sensitized else 1.0), 3)
        total += c
        drivers.append({"metric": f, "label": d["label"], "contribution": c})
    return round(total, 3), drivers


def _by_injury(metrics: dict, dev_by_metric: dict, sensitized: set) -> list:
    """Decompõe o risco POR DIAGNÓSTICO usando o mapa injury_taxonomy.DIAGNOSES (lesão→factors→
    source). Ranqueia da maior contribuição pra menor, cada item citando a `source` da taxonomia.

    HONESTIDADE (app de lesão): ausência de MEDIDA ≠ ausência de risco. Regra de avaliabilidade:
      - NENHUM factor da lesão medido na captura  → evaluable=false ("não avaliável"), NUNCA "baixo"
        (senão o vídeo lateral 'zeraria' pfp/itbs, cujos sinais só o vídeo de FRENTE mede);
      - só ALGUNS factors medidos                 → evaluable=true + partial=true (risco parcial);
      - TODOS medidos                             → evaluable=true, avaliação completa.
    Um factor medido e dentro do ideal conta como avaliado (band pode ser 'baixo' de verdade)."""
    out = []
    for dx, meta in DIAGNOSES.items():
        factors = meta["factors"]
        missing = [f for f in factors if metrics.get(f) is None]
        item = {"dx": dx, "label": meta["label"], "source": meta["source"]}
        if len(missing) == len(factors):          # nada medido → não avaliável (≠ baixo)
            needs_front = any(f in _FRONTAL_FACTORS for f in missing)
            item.update({"evaluable": False,
                         "reason": "precisa do vídeo de frente" if needs_front
                                   else "os fatores desta lesão não foram medidos nesta captura"})
        else:
            score, drivers = _injury_contrib(factors, dev_by_metric, sensitized)
            item.update({"evaluable": True, "partial": bool(missing), "score": score,
                         "band": _band(score), "drivers": drivers})
        out.append(item)
    # avaliáveis primeiro (score desc); não avaliáveis por último
    out.sort(key=lambda i: (i.get("evaluable", False), i.get("score", 0.0)), reverse=True)
    return out


def _band(score: float) -> str:
    """Faixa RELATIVA a partir do score ponderado (não é probabilidade)."""
    if score <= 0.0:
        return "baixo"
    if score < 1.5:
        return "moderado"
    if score < 4.0:
        return "elevado"
    return "alto"


def assess(metrics: dict, profile: Optional[dict] = None,
           history: Optional[dict] = None) -> dict:
    """Avalia o risco RELATIVO de lesão a partir das métricas de forma. Devolve a faixa + os
    fatores que a puxaram (do maior contribuinte pro menor) + o caveat honesto.

    `score` = Σ (severidade_do_desvio × peso_de_risco) sobre os fatores fora do ideal. Só
    considera o que o vídeo mediu (uma vista lateral não mede queda pélvica, e vice-versa —
    o quadro completo pede as duas vistas)."""
    targets = ideal_targets(profile, history)
    devs = diagnose(metrics, targets)   # já traz severity, source, plain, label, side

    # Lesão PRÉVIA é o preditor #1 de nova lesão (literatura): fatores ligados a uma lesão que o
    # atleta já teve entram SENSIBILIZADOS (peso maior) — o histórico passa a pesar no risco.
    sensitized = set((history or {}).get("factors", []))

    factors, score = [], 0.0
    for d in devs:
        weight = RISK_WEIGHT.get(d["metric"], 1.0)
        hit = d["metric"] in sensitized
        contribution = round(d["severity"] * weight * (SENSITIZE if hit else 1.0), 3)
        score += contribution
        factors.append({
            "metric": d["metric"], "label": d["label"], "value": d["value"],
            "unit": d["unit"], "side": d["side"], "source": d["source"],
            "plain": d["plain"], "weight": weight, "contribution": contribution,
            "sensitized": hit,   # True = você já teve lesão ligada a este fator
        })
    factors.sort(key=lambda f: f["contribution"], reverse=True)

    # Decomposição POR LESÃO (aditiva — não mexe nas chaves antigas). Reusa os MESMOS desvios já
    # calculados (severity de diagnose) indexados por métrica.
    dev_by_metric = {d["metric"]: d for d in devs}
    by_injury = _by_injury(metrics, dev_by_metric, sensitized)

    return {
        "risk_band": _band(score),      # baixo | moderado | elevado | alto (RELATIVO)
        "score": round(score, 2),       # score ponderado — NÃO é probabilidade
        "factors": factors,             # o que puxou o risco, do maior pro menor
        "by_injury": by_injury,         # risco decomposto POR DIAGNÓSTICO (ranqueado + honesto)
        "model": "literatura",          # 'literatura' (prior) hoje; 'treinado' quando houver dados
        "caveat": "Indicativo e RELATIVO — não é diagnóstico nem probabilidade de lesão. Reflete "
                  "quantos fatores estão fora do ideal e quão forte a ciência os liga a lesão. "
                  "Quadro completo pede a análise de lado E de frente.",
    }
