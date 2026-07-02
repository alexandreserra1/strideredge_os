"""analytics/coach.py — Coach Sintetico (LLM local via Ollama).

Gera um veredito a partir das metricas do treino. Roda 100% local — sem token.

Desenho OOP:
  - BaseLLMClient -> OllamaClient: POLIMORFISMO do "cerebro" (troca o modelo).
  - BaseAnalyzer  -> BreakingPoint/Efficiency/HrZone: POLIMORFISMO das analises.
  - Coach: COMPOE um LLM + uma lista de analisadores. Adicionar analise nova =
    passar mais um BaseAnalyzer na lista, sem mexer no Coach (aberto/fechado).
"""

import re

import httpx

from core.database import get_connection
from core.framework.interfaces import BaseLLMClient, BaseAnalyzer, BaseRetriever, BaseGuard
from analytics.run_analysis import (
    BreakingPointAnalyzer, EfficiencyAnalyzer, TerrainContextAnalyzer,
    CadenceReferenceAnalyzer, DurabilityAnalyzer,
)
from analytics.intensity import HrZoneAnalyzer
from analytics.athlete import AthleteHistoryAnalyzer
from analytics.training_load import AcwrAnalyzer
from analytics.fitness import FitnessAnalyzer
from analytics.grounding import GroundingGuard
from rag.knowledge_base import KnowledgeBase


class OllamaClient(BaseLLMClient):
    """Cliente do LLM local servido pelo Ollama (implementa BaseLLMClient)."""

    def __init__(self, model: str = "qwen2.5:7b-instruct",
                 url: str = "http://localhost:11434/api/chat", temperature: float = 0.2):
        self.model = model
        self.url = url
        self.temperature = temperature   # baixa = mais factual; 0 = deterministico (eval)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        response = httpx.post(
            self.url,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": self.temperature},
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


class VerdictParser:
    """Divide o veredito (as 3 partes que o SYSTEM_PROMPT exige) em campos p/ a API/UI.

    Parse DETERMINISTICO: o codigo estrutura — nao pedimos JSON ao LLM (degradaria a prosa
    e fugiria da filosofia conclusao-pronta). Robusto a variacoes de markdown (###, **, 1./1));
    sem secoes reconheciveis, devolve listas vazias + texto integral (a UI degrada gracioso).
    """

    _HEADER = re.compile(
        r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:\d[.)]\s*)?"
        r"(pontos?\s+fortes|pontos?\s+a\s+melhorar|o\s+que\s+fazer)\b", re.I)
    _BULLET = re.compile(r"^\s*[-*•]\s*")
    _KEY = {"fortes": "strengths", "melhorar": "improvements", "fazer": "actions"}

    @classmethod
    def _clean(cls, line: str) -> str:
        # tira bullet, negrito e asteriscos residuais ('**Fonte**' -> 'Fonte')
        return cls._BULLET.sub("", line).replace("**", "").strip().strip("*").strip()

    def parse(self, text: str) -> dict:
        out = {"verdict": text, "strengths": [], "improvements": [], "actions": [],
               "citations": GroundingGuard.citations(text)}   # reusa a primitiva
        bucket = None
        for line in text.splitlines():
            m = self._HEADER.match(line)
            if m:
                kw = next(k for k in self._KEY if k in m.group(1).lower())
                bucket = self._KEY[kw]
                continue
            clean = self._clean(line)
            if bucket is None or not clean:
                continue
            if clean.lower().startswith("fonte"):
                continue   # linhas 'Fonte(s): ...' ja viram citations
            if self._BULLET.match(line) or not out[bucket]:
                out[bucket].append(clean)          # novo item (bullet ou 1o paragrafo)
            else:
                out[bucket][-1] += " " + clean     # continuacao do item anterior
        return out


# Lista padrao de analises que entram no veredito. Para incluir uma nova,
# basta adicionar outro BaseAnalyzer aqui — o Coach nao muda.
DEFAULT_ANALYZERS = [
    BreakingPointAnalyzer(), EfficiencyAnalyzer(), DurabilityAnalyzer(),
    TerrainContextAnalyzer(), CadenceReferenceAnalyzer(), HrZoneAnalyzer(),
    AthleteHistoryAnalyzer(),   # personalização: compara com o histórico do atleta
    AcwrAnalyzer(),             # carga acumulada / risco de lesão (ACWR)
    FitnessAnalyzer(),          # previsão de prova (Riegel) + tendência de fitness
]


class Coach:
    """Gera o veredito de um treino. COMPOE um LLM + uma lista de analisadores."""

    SYSTEM_PROMPT = (
        "Voce e um treinador de corrida experiente e DIDATICO. Ensine o atleta: explique o porque "
        "em linguagem simples, sem jargao e sem platitude.\n"
        "ESTRUTURE em 3 partes, cada uma com UMA ou DUAS frases (a explicacao vai JUNTO, nunca em "
        "secao separada de 'explicacao'):\n"
        "1. Pontos fortes — o que foi bem, com o dado que mostra.\n"
        "2. Pontos a melhorar — onde falhou e por que importa.\n"
        "3. O que fazer — acoes concretas, cada uma explicada e (se houver) com a fonte citada.\n"
        "REGRAS:\n"
        "- Baseie tudo SOMENTE nos dados/evidencias; cite a fonte (PMC) ao usar uma.\n"
        "- Ao prescrever treino, descreva-o QUALITATIVAMENTE — NUNCA com series, repeticoes, minutos, "
        "ritmo ou bpm. ERRADO: '3 series de 5min a 170 spm'. CERTO: 'tiros curtos de passada rapida "
        "com pausa para recuperar'.\n"
        "- NUNCA invente nem calcule numeros. Use so os que aparecem nos dados/conclusoes; se faltar, "
        "descreva em palavras. Para intensidade use termos QUALITATIVOS ('ritmo de conversa', 'bem leve').\n"
        "- PROIBIDO citar desidratacao, calor, glicogenio ou clima (nao sao medidos). "
        "ERRADO: 'pode ser desidratacao'. CERTO: 'sinal de fadiga'.\n"
        "- Seja CONCISO: no MAXIMO ~110 palavras no total. NAO repita pontos nem crie secao de 'explicacao'.\n"
        "Responda em portugues."
    )

    def __init__(self, llm: BaseLLMClient, analyzers: list = None,
                 knowledge: BaseRetriever = None, web: BaseRetriever = None, k: int = 3,
                 guard: BaseGuard = None, parser: "VerdictParser" = None):
        self.llm = llm                              # cerebro injetado (composicao)
        self.analyzers = analyzers or DEFAULT_ANALYZERS
        self.knowledge = knowledge                  # base curada (opcional)
        self.web = web                              # fallback de web (opcional)
        self.k = k
        self.guard = guard or GroundingGuard()      # guarda de aterramento (composicao)
        self.parser = parser or VerdictParser()     # estrutura o veredito p/ a API (composicao)

    def _header(self, activity_id: str) -> str:
        """Cabecalho do prompt: metadados basicos do treino."""
        con = get_connection()
        row = con.execute(
            """SELECT a.activity_name, a.primary_type, a.total_distance_meters,
                      a.total_duration_seconds, c.avg_hr, c.avg_cadence
               FROM dim_activities a
               LEFT JOIN cache_workout_summary c ON c.activity_id = a.activity_id
               WHERE a.activity_id = ?""",
            [activity_id],
        ).fetchone()
        name, ptype, dist, dur, avg_hr, avg_cad = row
        return (
            f"Treino: {name} ({ptype})\n"
            f"Distancia: {round((dist or 0)/1000, 2)} km | "
            f"Duracao: {round((dur or 0)/60, 1)} min\n"
            f"FC media: {round(avg_hr) if avg_hr else '-'} bpm | "
            f"Cadencia media: {round(avg_cad) if avg_cad else '-'} passos/min"
        )

    def build_user_prompt(self, activity_id: str) -> str:
        """Cabecalho + linhas dos analisadores + evidencias do RAG (se houver)."""
        linhas = [self._header(activity_id)]
        metricas = []
        for analyzer in self.analyzers:
            linha = analyzer.to_prompt(analyzer.analyze(activity_id))
            if linha:
                linhas.append(linha)
                metricas.append(linha)

        # RAG: query = resumo das metricas. Tenta a base CURADA; se vier vazia,
        # cai pro fallback de WEB (dominios confiaveis). Marca a origem.
        query = " ".join(metricas)
        hits = []
        if self.knowledge is not None:
            hits = self.knowledge.retrieve(query, k=self.k)
        if not hits and self.web is not None:
            hits = self.web.retrieve(query, k=self.k)

        if hits:
            linhas.append("\nEvidencias (cite a fonte ao usar):")
            for i, h in enumerate(hits, 1):
                tag = "" if h.get("origin") == "curado" else " [web, nao curado]"
                linhas.append(f"{i}. {h['text']} [FONTE: {h['source']}{tag}]")
        else:
            linhas.append("\n(Sem evidencia relevante na base curada nem na web.)")

        return "\n".join(linhas)

    def verdict(self, activity_id: str) -> str:
        """Monta o prompt e gera o veredito com a guarda de aterramento (retry se inventar)."""
        prompt = self.build_user_prompt(activity_id)
        return self.guard.enforce(self.llm, self.SYSTEM_PROMPT, prompt)

    def structured_verdict(self, activity_id: str) -> dict:
        """Veredito ESTRUTURADO p/ a API/UI: texto + fortes/melhorar/fazer + citacoes."""
        return self.parser.parse(self.verdict(activity_id))


if __name__ == "__main__":
    from rag.knowledge_base import OllamaEmbedder
    from rag.web_search import WebSearchRetriever
    con = get_connection()
    aid = con.execute("SELECT activity_id FROM dim_activities WHERE activity_name='Corrida Floripa'").fetchone()[0]
    # injeta o cerebro (LLM), a base curada (RAG) e o fallback de web
    coach = Coach(
        llm=OllamaClient(),
        knowledge=KnowledgeBase(embedder=OllamaEmbedder()),
        web=WebSearchRetriever(),
    )
    print("=== Prompt (com evidencias do RAG) ===")
    print(coach.build_user_prompt(aid))
    print("\n=== Veredito do Coach (aterrado + citado) ===")
    print(coach.verdict(aid))
