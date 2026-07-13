"""analytics/form_coach.py — Algoritmo Corretivo: do gap biomecânico -> exercícios citados.

Fecha o ciclo "vê o movimento -> entende -> age". Recebe as métricas do motor de vídeo
(FormMetrics) + o perfil do atleta, calcula os alvos ideais e o gap (analytics/biomechanics),
recupera a evidência do corpus (RAG) e o LLM local transforma isso em um plano de correção
COM fonte. Reusa a mesma disciplina do veredito: `GroundingGuard` (sem número inventado) e
`VerdictParser` (saída estruturada). Sem evidência no corpus, não inventa exercício.
"""

import re
from typing import Optional

from core.framework.interfaces import BaseLLMClient, BaseRetriever
from analytics.grounding import GroundingGuard
from analytics.biomechanics import ideal_targets, diagnose


# O QUE corrigir (os desvios) ja vem estruturado do biomechanics.py — deterministico.
# O LLM faz SO uma coisa: propor os EXERCICIOS que corrigem, aterrado nas evidencias.
SYSTEM = (
    "Voce e um treinador de corrida que analisa BIOMECANICA por video, didatico e direto. "
    "Recebe os desvios ja medidos e EVIDENCIAS cientificas. Sua unica tarefa: listar "
    "exercicios ou ajustes praticos que corrijam esses desvios, UM POR LINHA, cada linha "
    "comecando com '- ' e terminando com a fonte entre parenteses no formato (Fonte: PMCxxxx). "
    "Regras rigidas: cada linha ataca UM dos desvios LISTADOS — se a evidencia mencionar outra "
    "metrica que NAO esta na lista de desvios (ex: cita cadencia mas cadencia nao foi listada), "
    "IGNORE essa parte, nao recomende sobre ela. NAO escreva cabecalhos nem repita os desvios; "
    "NAO use markdown; use SOMENTE numeros que aparecem nos dados; recomende SOMENTE o que as "
    "evidencias amparam e cite a FONTE (PMC) de cada exercicio. Sem evidencia p/ um desvio, nao invente."
)


class FormCoach:
    """Plano corretivo a partir das métricas de forma (composição: LLM + RAG + guarda)."""

    def __init__(self, llm: BaseLLMClient, knowledge: Optional[BaseRetriever] = None, k: int = 4):
        self.llm = llm
        self.knowledge = knowledge
        self.k = k
        self.guard = GroundingGuard()

    # remove o "(Fonte: PMCxxxx)" cru do texto do exercício — a fonte vira chip legível na UI
    _FONTE_RE = re.compile(r"\s*[\(\[]?\s*fonte:?\s*PMC\d+\s*[\)\]]?\.?\s*$", re.IGNORECASE)

    @classmethod
    def _drills(cls, text: str) -> list:
        """Extrai os exercícios (uma linha cada) da resposta do LLM, limpando bullets, o
        sufixo '(Fonte: PMC...)' e descartando cabeçalhos que o modelo eventualmente insira."""
        out = []
        for line in text.splitlines():
            s = line.strip().lstrip("-•*").strip()
            low = s.lower()
            if len(s) < 8:
                continue
            if low.startswith(("a melhorar", "o que fazer", "desvios", "exercicios", "exercícios")):
                continue
            s = cls._FONTE_RE.sub("", s).strip()   # tira "(Fonte: PMCxxxx)" do fim
            if s:
                out.append(s)
        return out

    def _prompt(self, metrics: dict, devs: list, hits: list) -> str:
        linhas = ["Desvios medidos (medido vs faixa ideal):"]
        for d in devs[:4]:
            faixa = f"<= {d['hi']:g}" if d["side"] == "alto" else f">= {d['lo']:g}"
            linhas.append(f"- {d['label']}: medido {d['value']:g}{d['unit']} "
                          f"(ideal {faixa}{d['unit']}) [FONTE: {d['source']}]")
        if hits:
            linhas.append("\nEvidencias (cite a FONTE ao recomendar):")
            for i, h in enumerate(hits, 1):
                linhas.append(f"{i}. {h['text']} [FONTE: {h['source']}]")
        else:
            linhas.append("\n(Sem evidencia relevante na base — nao invente exercicios.)")
        return "\n".join(linhas)

    def plan(self, metrics: dict, profile: Optional[dict] = None,
             history: Optional[dict] = None) -> dict:
        """Devolve {verdict, actions, citations, targets, deviations}. Os DESVIOS (o que
        corrigir) sao deterministicos; o LLM so gera os exercicios (aterrados + citados)."""
        targets = ideal_targets(profile, history)
        devs = diagnose(metrics, targets)

        if not devs:
            return {
                "verdict": "Sua forma esta dentro das faixas ideais nas metricas medidas. "
                           "Mantenha o trabalho e refaca a analise conforme evoluir.",
                "actions": [], "citations": [], "targets": targets, "deviations": [],
            }

        query = " ".join(d["query"] for d in devs[:3])
        hits = self.knowledge.retrieve(query, k=self.k) if self.knowledge is not None else []
        prompt = self._prompt(metrics, devs, hits)

        text = self.guard.enforce(self.llm, SYSTEM, prompt)
        issues = self.guard.issues(text, prompt + " " + " ".join(h["text"] for h in hits))
        if issues["invented_numbers"] or issues["banned_causes"]:
            text = self.guard.enforce(self.llm, SYSTEM, prompt, first=text)

        return {
            "verdict": text,
            "actions": self._drills(text),
            "citations": GroundingGuard.citations(text),
            "targets": targets,
            "deviations": devs,
        }
