"""analytics/training_plan.py — gerador de PLANO CORRETIVO faseado (determinístico + citado).

Do gap medido → um programa de N semanas que ataca os desvios do atleta EM ORDEM DE RISCO,
sequenciando as FASES da biblioteca de exercícios (ativação/mobilidade → força → drill de marcha)
com progressão gradual (~10%/semana). Mesma filosofia do coach: prescrição determinística e
citada; o LLM só redige a "capa" humana (não inventa exercício). Reusa `analytics.exercises`
(biblioteca faseada) e os fatores JÁ priorizados por contribuição pelo `injury_risk.assess`.
"""

from typing import Optional

from analytics.exercises import for_factors
from analytics.injury_quality import sanitize_metrics
from analytics.injury_risk import assess

# Bloco temporal de cada fase: 0 = base (desde a 1ª semana); 1 = força (no 1/3); 2 = drill de
# marcha (no 2/3, sobre a base de força). Sequência corretiva padrão (ativar → fortalecer → treinar).
_BLOCK = {"ativacao": 0, "mobilidade": 0, "forca": 1, "drill": 2}
_DOSE = {"ativacao": "2×15", "mobilidade": "2×30s por lado",
         "forca": "3×10 (progride carga ~10%/sem)", "drill": "8–10 min numa corrida leve"}


def _block_start(weeks: int, present: list) -> dict:
    """Semana de início de cada bloco PRESENTE, espaçado ao longo do programa. Se um bloco não tem
    exercício, os que existem se ANTECIPAM (não deixa semana vazia) — ex.: só cadência (drill) →
    começa na 1ª semana, não espera uma base de força que não será construída."""
    ordered = sorted(set(present))
    n = len(ordered) or 1
    return {b: (1 if i == 0 else max(2, (i * weeks) // n + 1)) for i, b in enumerate(ordered)}


def build_plan(risk_factors: list, weeks: int = 6) -> dict:
    """`risk_factors` = fatores desviados ORDENADOS por contribuição (saída de `assess`; já embute
    perfil+histórico). Devolve o programa faseado: cada semana com bloco + foco + sessões
    (exercício, dose, fonte). Determinístico e citado."""
    weeks = max(2, min(int(weeks or 6), 16))
    priority = [f["metric"] for f in (risk_factors or [])]
    exs = for_factors(priority)
    if not exs:
        return {"duration_weeks": weeks, "weeks": [], "priority": [],
                "caveat": "Nenhum desvio com exercício citado na biblioteca — mantenha o trabalho "
                          "e reavalie por vídeo conforme evoluir."}

    # ordena por prioridade do fator que o exercício ataca (menor índice = mais grave), depois por bloco
    def _prio(e):
        idx = min((priority.index(f) for f in e["targets"] if f in priority), default=99)
        return (idx, _BLOCK.get(e["phase"], 0))
    exs = sorted(exs, key=_prio)
    present = [_BLOCK.get(e["phase"], 0) for e in exs]
    starts = _block_start(weeks, present)
    top_label = next((f["label"] for f in risk_factors if f["metric"] in priority), "sua forma")
    _BLOCO_LABEL = {0: "base", 1: "forca", 2: "drill_de_marcha"}

    plan = []
    for n in range(1, weeks + 1):
        sessions = [
            {"exercise": e["name"], "phase": e["phase"], "dose": _DOSE.get(e["phase"], ""),
             "source": e["source"]}
            for e in exs if starts[_BLOCK.get(e["phase"], 0)] <= n
        ]
        started = [b for b in starts if starts[b] <= n]   # bloco mais avançado já iniciado
        bloco = _BLOCO_LABEL[max(started)] if started else "base"
        plan.append({"n": n, "bloco": bloco, "focus": top_label, "sessions": sessions})

    intro = (f"Seu foco principal agora é {top_label.lower()}. Este plano de {weeks} semanas vai por "
             "partes: primeiro ATIVA os músculos certos, depois FORTALECE, e no fim TREINA o gesto na "
             "corrida. Sem pressa — um estímulo por vez, e a gente reavalia por vídeo.")
    return {
        "duration_weeks": weeks,
        "priority": [{"metric": f["metric"], "label": f["label"]} for f in risk_factors[:3]],
        "intro": intro,
        "weeks": plan,
        "caveat": "Plano corretivo GRADUAL: suba o volume ~10% por semana, um estímulo por vez. "
                  "Reavalie por vídeo a cada 2–3 semanas. Não é prescrição médica — se doer, "
                  "reduza a carga e procure avaliação.",
    }


def plan_from_metrics(metrics: dict, weeks: int = 6, profile: Optional[dict] = None,
                      history: Optional[dict] = None) -> dict:
    """Orquestra: métricas do vídeo → plano corretivo. Reusa a sanitização (dado impossível) e o
    risco (assess, já com perfil+histórico). Não constrói plano sobre captura não confiável."""
    metrics, _ = sanitize_metrics(metrics)
    if metrics.get("reliable") is False:
        return {"unreliable": True, "duration_weeks": 0, "weeks": [], "priority": [],
                "intro": "", "caveat": metrics.get("quality_note")
                or "A captura não ficou boa o bastante — refilme e gere o plano de novo."}
    risk = assess(metrics, profile, history)
    return build_plan(risk["factors"], weeks)
