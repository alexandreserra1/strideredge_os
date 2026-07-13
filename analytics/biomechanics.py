"""analytics/biomechanics.py — alvos biomecânicos PERSONALIZADOS + diagnóstico de gap.

Funções puras (fáceis de testar): partem das faixas da literatura (corpus RAG) e ajustam
pelo contexto do atleta (morfologia/histórico). O `diagnose` compara o MEDIDO (FormMetrics
do motor) com o IDEAL e devolve os desvios priorizados — insumo do algoritmo corretivo.

Nada de LLM aqui: é aritmética aterrada. O coach (form_coach.py) transforma os desvios em
exercícios citados. Cada alvo carrega a FONTE do corpus pra manter a rastreabilidade.
"""

from typing import Optional


# faixa-base da literatura + direção do "melhor" + fonte (PMC do corpus)
def ideal_targets(profile: Optional[dict] = None, history: Optional[dict] = None) -> dict:
    """Alvos ideais por métrica. Ajusta pelo atleta quando há perfil; senão usa defaults
    populacionais. Ex.: corredor mais alto tende naturalmente a cadência um pouco menor."""
    p = profile or {}
    height = p.get("height_cm")

    # piso de cadência cai ~0.3 spm por cm acima de 175 (mais alto = passada mais longa)
    cad_floor = 170.0
    if height:
        cad_floor = round(170.0 - max(0.0, (height - 175.0)) * 0.3, 1)

    return {
        "cadence_spm": {"lo": cad_floor, "hi": 190.0, "unit": "spm", "dir": "higher_better",
                        "source": "PMC12440572",
                        "label": "cadência"},
        "ground_contact_ms": {"lo": 0.0, "hi": 250.0, "unit": "ms", "dir": "lower_better",
                              "source": "PMC3944563", "label": "tempo de contato com o solo"},
        "vertical_oscillation_pct": {"lo": 0.0, "hi": 8.0, "unit": "%", "dir": "lower_better",
                                     "source": "PMC11127892", "label": "oscilação vertical"},
        "knee_contact_deg": {"lo": 0.0, "hi": 174.0, "unit": "°", "dir": "lower_better",
                             "source": "PMC9441414", "label": "flexão do joelho no apoio"},
        "trunk_lean_deg": {"lo": 5.0, "hi": 14.0, "unit": "°", "dir": "range",
                           "source": "PMC11135760", "label": "inclinação do tronco"},
        "asymmetry_pct": {"lo": 0.0, "hi": 10.0, "unit": "%", "dir": "lower_better",
                          "source": "PMC7241633", "label": "assimetria E/D"},
    }


# explicação em LINGUAGEM DE GENTE do que o desvio significa (por métrica + lado).
# É o que a UI mostra pro atleta — sem jargão, sem número solto.
PLAIN = {
    ("cadence_spm", "baixo"): "Seus passos estão um pouco longos e lentos. Dar passos mais "
        "curtos e rápidos faz o pé cair embaixo do corpo e amortece melhor o impacto.",
    ("ground_contact_ms", "alto"): "Seu pé fica tempo demais no chão a cada passada — falta "
        "'mola'. Correr mais leve e reativo devolve energia mais rápido.",
    ("vertical_oscillation_pct", "alto"): "Você sobe e desce demais a cada passo. Essa energia "
        "está indo pra cima em vez de pra frente — dá pra correr mais 'rasante'.",
    ("knee_contact_deg", "alto"): "Seu joelho está quase reto quando o pé toca o chão (passada "
        "longa demais). Isso joga o impacto direto na articulação, sem amortecer.",
    ("trunk_lean_deg", "baixo"): "Você corre muito ereto, quase 'sentado'. Uma leve inclinação "
        "do tronco pra frente aproveita a gravidade e tira peso do freio.",
    ("trunk_lean_deg", "alto"): "Você inclina o tronco pra frente demais, o que sobrecarrega a "
        "lombar. O ideal é uma inclinação suave, a partir do tornozelo.",
    ("asymmetry_pct", "alto"): "Há uma diferença grande entre a perna esquerda e a direita — um "
        "lado está trabalhando mais que o outro (pode ser fadiga ou compensação).",
}


# tema de busca no corpus p/ cada métrica desviada (o corretivo recupera por aqui)
CORRECTIVE_QUERY = {
    "cadence_spm": "aumentar cadencia frequencia de passos metronomo reeducacao de marcha",
    "ground_contact_ms": "reduzir tempo de contato com o solo pliometria rigidez elastica",
    "vertical_oscillation_pct": "reduzir oscilacao vertical correr rasante economia de corrida",
    "knee_contact_deg": "overstriding passada longa aterrar sob o quadril aumentar cadencia",
    "trunk_lean_deg": "inclinacao do tronco postura patelofemoral",
    "asymmetry_pct": "assimetria contato solo fortalecer quadril gluteo medio",
}


def diagnose(metrics: dict, targets: dict) -> list:
    """Compara o medido × alvo. Devolve desvios (fora da faixa) ordenados do pior pro
    melhor. `severity` = quão longe da faixa, normalizado pela largura (comparável entre
    métricas de unidades diferentes)."""
    out = []
    for key, t in targets.items():
        v = metrics.get(key)
        if v is None:
            continue
        lo, hi = t["lo"], t["hi"]
        if v < lo:
            side, gap = "baixo", lo - v
        elif v > hi:
            side, gap = "alto", v - hi
        else:
            continue
        width = max(hi - lo, 1e-6)
        out.append({
            "metric": key, "label": t["label"], "value": v, "lo": lo, "hi": hi,
            "unit": t["unit"], "side": side, "source": t["source"],
            "severity": round(gap / width, 3),
            "query": CORRECTIVE_QUERY.get(key, t["label"]),
            "plain": PLAIN.get((key, side), ""),   # explicação em linguagem de gente
        })
    out.sort(key=lambda d: d["severity"], reverse=True)
    return out
