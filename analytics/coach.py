"""analytics/coach.py — Coach Sintetico (LLM local via Ollama).

Gera um veredito a partir das metricas do treino. Roda 100% local — sem token.

Desenho OOP:
  - BaseLLMClient -> OllamaClient: POLIMORFISMO do "cerebro" (troca o modelo).
  - BaseAnalyzer  -> BreakingPoint/Efficiency/HrZone: POLIMORFISMO das analises.
  - Coach: COMPOE um LLM + uma lista de analisadores. Adicionar analise nova =
    passar mais um BaseAnalyzer na lista, sem mexer no Coach (aberto/fechado).
"""

import httpx

from core.database import get_connection
from core.framework.interfaces import BaseLLMClient, BaseAnalyzer, BaseRetriever
from analytics.run_analysis import (
    BreakingPointAnalyzer, EfficiencyAnalyzer, TerrainContextAnalyzer,
    CadenceReferenceAnalyzer,
)
from analytics.intensity import HrZoneAnalyzer
from analytics.athlete import AthleteHistoryAnalyzer
from analytics.training_load import AcwrAnalyzer
from analytics.fitness import FitnessAnalyzer
from rag.knowledge_base import KnowledgeBase


class OllamaClient(BaseLLMClient):
    """Cliente do LLM local servido pelo Ollama (implementa BaseLLMClient)."""

    def __init__(self, model: str = "qwen2.5:7b-instruct",
                 url: str = "http://localhost:11434/api/chat"):
        self.model = model
        self.url = url

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
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


# Lista padrao de analises que entram no veredito. Para incluir uma nova,
# basta adicionar outro BaseAnalyzer aqui — o Coach nao muda.
DEFAULT_ANALYZERS = [
    BreakingPointAnalyzer(), EfficiencyAnalyzer(),
    TerrainContextAnalyzer(), CadenceReferenceAnalyzer(), HrZoneAnalyzer(),
    AthleteHistoryAnalyzer(),   # personalização: compara com o histórico do atleta
    AcwrAnalyzer(),             # carga acumulada / risco de lesão (ACWR)
    FitnessAnalyzer(),          # previsão de prova (Riegel) + tendência de fitness
]


class Coach:
    """Gera o veredito de um treino. COMPOE um LLM + uma lista de analisadores."""

    SYSTEM_PROMPT = (
        "Voce e um treinador de elite especialista em corrida e provas hibridas "
        "(Hyrox, Crossfit Endurance). Analise os numeros do treino e devolva um "
        "feedback direto, firme e tecnico — sem rodeios.\n"
        "REGRAS IMPORTANTES:\n"
        "- Baseie recomendacoes SOMENTE nas evidencias cientificas fornecidas e nos "
        "dados do atleta. Use as faixas de FC reais (nao presuma limites).\n"
        "- Ao usar uma evidencia, CITE a fonte entre parenteses.\n"
        "- Se nao houver evidencia relevante para um ponto, diga que nao ha evidencia "
        "suficiente — NAO invente numeros, faixas ou limiares.\n"
        "- Quando uma linha CONCLUSAO ja vier pronta (ex: cadencia vs limiar), use-a "
        "diretamente. NAO recalcule se um valor esta acima/abaixo de um limiar.\n"
        "Responda em portugues, em no maximo 3 paragrafos curtos."
    )

    def __init__(self, llm: BaseLLMClient, analyzers: list = None,
                 knowledge: BaseRetriever = None, web: BaseRetriever = None, k: int = 3):
        self.llm = llm                              # cerebro injetado (composicao)
        self.analyzers = analyzers or DEFAULT_ANALYZERS
        self.knowledge = knowledge                  # base curada (opcional)
        self.web = web                              # fallback de web (opcional)
        self.k = k

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
        """Monta o prompt e chama o LLM."""
        return self.llm.chat(self.SYSTEM_PROMPT, self.build_user_prompt(activity_id))


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
