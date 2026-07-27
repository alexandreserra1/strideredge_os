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
_BLOCO_LABEL = {0: "base", 1: "forca", 2: "drill_de_marcha"}
_BLOCO_TITULO = {0: "Base — ativar", 1: "Força — fortalecer", 2: "Drill de marcha — treinar o gesto"}
# POR QUE de cada fase (explicativo, na ordem corretiva) — didático, sem jargão.
_BLOCO_PORQUE = {
    0: "Antes de exigir força, a gente ACORDA os músculos certos: exercícios leves pro corpo "
       "aprender a recrutá-los. É a fundação — parece pouco, mas é o que faz o resto pegar.",
    1: "Agora que os músculos acordaram, a gente os deixa MAIS FORTES. É a base que sustenta a "
       "passada; sem ela, o gesto novo não segura sob cansaço. Sobe de leve a cada semana.",
    2: "Com a força na conta, agora TREINA o gesto correndo — pra a correção virar AUTOMÁTICA, "
       "algo que o corpo faz sozinho, não que você fica pensando o tempo todo.",
}
# Progressão de dose por fase (concreta e honesta — o que muda ao longo das semanas).
_PROGRESSAO = {
    "ativacao": "2 séries de 15, dia sim dia não. Foco em fazer certo, não em quantidade.",
    "mobilidade": "2×30s por lado, todo dia. Constância vale mais que intensidade aqui.",
    "forca": "Comece em 3 séries de 10. A cada semana, suba um pouco — mais 1–2 repetições ou um "
             "pouco de carga (~10%). Se travar, segura no mesmo peso mais uma semana.",
    "drill": "Comece com 8 minutos numa corrida leve e vá até uns 12 conforme fica natural. "
             "Qualidade do gesto acima de tudo — se perder a forma, pare e retome depois.",
}


def _block_start(weeks: int, present: list) -> dict:
    """Semana de início de cada bloco PRESENTE, espaçado ao longo do programa. Se um bloco não tem
    exercício, os que existem se ANTECIPAM (não deixa semana vazia) — ex.: só cadência (drill) →
    começa na 1ª semana, não espera uma base de força que não será construída."""
    ordered = sorted(set(present))
    n = len(ordered) or 1
    return {b: (1 if i == 0 else max(2, (i * weeks) // n + 1)) for i, b in enumerate(ordered)}


def build_plan(risk_factors: list, weeks: int = 6) -> dict:
    """`risk_factors` = fatores desviados ORDENADOS por contribuição (saída de `assess`; já embute
    perfil+histórico). Devolve o programa faseado POR FASE (não por semana): cada fase com o PORQUE
    dela + seus exercícios (cada um UMA vez, com 'como fazer' e progressão). Determinístico e citado.
    Estruturar por fase (e não repetir o exercício toda semana) deixa o plano explicativo em vez de
    redundante."""
    weeks = max(2, min(int(weeks or 6), 16))
    priority = [f["metric"] for f in (risk_factors or [])]
    exs = for_factors(priority)
    if not exs:
        return {"duration_weeks": weeks, "phases": [], "priority": [],
                "caveat": "Não achei nada pra corrigir com respaldo científico agora — mantenha o "
                          "bom trabalho e grave um vídeo novo mais pra frente pra reconferir."}

    # ordena por prioridade do fator que o exercício ataca (menor índice = mais grave), depois por bloco
    def _prio(e):
        idx = min((priority.index(f) for f in e["targets"] if f in priority), default=99)
        return (idx, _BLOCK.get(e["phase"], 0))
    exs = sorted(exs, key=_prio)
    present = sorted({_BLOCK.get(e["phase"], 0) for e in exs})
    starts = _block_start(weeks, present)
    top_label = next((f["label"] for f in risk_factors if f["metric"] in priority), "sua forma")

    # Agrupa POR FASE. Cada fase: janela de semanas (início → antes do próximo bloco) + porquê +
    # exercícios (uma vez cada, com como fazer + progressão). Sem repetir nada semana a semana.
    phases = []
    for i, b in enumerate(present):
        start = starts[b]
        end = (starts[present[i + 1]] - 1) if i + 1 < len(present) else weeks
        semanas = f"Semana {start}" if start == end else f"Semanas {start}–{end}"
        exercicios = [
            {"exercise": e["name"], "how": e.get("how", ""), "source": e["source"],
             "progression": _PROGRESSAO.get(e["phase"], "")}
            for e in exs if _BLOCK.get(e["phase"], 0) == b
        ]
        phases.append({
            "key": _BLOCO_LABEL[b], "title": _BLOCO_TITULO[b], "weeks_label": semanas,
            "why": _BLOCO_PORQUE[b], "focus": top_label, "exercises": exercicios,
        })

    intro = (f"Seu foco principal agora é {top_label.lower()}. Este plano de {weeks} semanas vem em "
             "etapas, na ordem certa: primeiro a gente ACORDA os músculos que estavam dormindo, "
             "depois os DEIXA MAIS FORTES, e no fim TREINA esse gesto correndo pra virar automático. "
             "Sem pressa — uma coisa de cada vez, e a gente confere de novo pelo vídeo.")
    return {
        "duration_weeks": weeks,
        "priority": [{"metric": f["metric"], "label": f["label"]} for f in risk_factors[:3]],
        "intro": intro,
        "phases": phases,
        "caveat": "Vá com calma: aumente o esforço só uns 10% por semana, uma novidade de cada vez — "
                  "assim o corpo se adapta sem sustos. Grave um vídeo novo a cada 2 ou 3 semanas pra "
                  "ver a evolução. Isto não substitui um médico: se sentir dor, alivie a carga e "
                  "procure um profissional.",
    }


def plan_from_metrics(metrics: dict, weeks: int = 6, profile: Optional[dict] = None,
                      history: Optional[dict] = None) -> dict:
    """Orquestra: métricas do vídeo → plano corretivo. Reusa a sanitização (dado impossível) e o
    risco (assess, já com perfil+histórico). Não constrói plano sobre captura não confiável."""
    metrics, _ = sanitize_metrics(metrics)
    if metrics.get("reliable") is False:
        return {"unreliable": True, "duration_weeks": 0, "phases": [], "priority": [],
                "intro": "", "caveat": metrics.get("quality_note")
                or "A captura não ficou boa o bastante — refilme e gere o plano de novo."}
    risk = assess(metrics, profile, history)
    return build_plan(risk["factors"], weeks)
