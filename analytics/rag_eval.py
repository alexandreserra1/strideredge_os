"""analytics/rag_eval.py — avaliação do RAG (retrieval) + LLM-as-judge.

Mede a QUALIDADE da recuperação da base científica (o RAG que aterra o plano corretivo
do FormCoach) — sem depender de nenhum coach de treino. "Eval-driven": mede ANTES de
mexer em prompt/corpus, pra iterar sem achismo.

Peças:
  - GOLDEN_RETRIEVAL: casos-ouro pergunta -> fonte esperada (PMC). Fonte única (os testes
    importam daqui).
  - RagBenchmark: recebe um retriever (KnowledgeBase) e reporta Context Recall (hit-rate) +
    Context Precision — os nomes canônicos do RAGAS, sem instalar o pacote.
  - LLMJudge: LLM-as-judge pontuando qualidades subjetivas de um texto gerado (acionabilidade,
    aterramento, relevância). Genérico: julga (fatos, veredito) — serve o plano corretivo.
"""

import json
import re


# Casos-ouro de retrieval (pergunta do atleta -> fonte esperada). FONTE UNICA:
# os testes importam daqui. O corpus é de ciência de corrida/biomecânica/lesão — o mesmo
# que aterra o plano corretivo do FormCoach.
# (pergunta, fonte esperada, domains). `domains`: ROTEAMENTO como a produção faz — query de desvio
# biomecânico consulta os domínios certos (evita bleed do corpus multi-domínio). None = sem rota.
GOLDEN_RETRIEVAL = [
    ("minha passada esta lenta, risco de me machucar?", "PMC12440572", ["biomecanica", "treino"]),  # cadencia
    ("aumentei muito a carga essa semana, perigo?", "PMC7047972", None),        # ACWR
    ("como distribuir intensidade dos treinos?", "PMC11679080", None),          # polarizado
    ("estou quicando muito ao correr, gasto energia?", "PMC11127892", None),    # economia/oscilacao
    ("minha FC sobe sozinha no fim do treino longo", "PMC12271085", ["treino"]),  # deriva cardiaca
    ("quanto dormir para recuperar melhor?", "PMC10354314", None),              # sono/recuperacao
    ("qual o jeito certo de construir base aerobica devagar?", "PMC11986187", None),  # zona 2
    ("musculacao ajuda a correr melhor?", "PMC11052887", None),                 # forca x economia
    ("quanto comer de acucar numa prova longa?", "PMC4008807", None),           # fueling carboidrato
    ("treinar no calor atrapalha? da pra me adaptar?", "PMC6890862", None),     # calor/aclimatacao
]
OFFTOPIC_QUERY = "qual a melhor receita de panqueca?"


class RagBenchmark:
    """Boletim de qualidade do RAG (retrieval). COMPÕE um retriever (KnowledgeBase)."""

    def __init__(self, knowledge):
        self.kb = knowledge

    def retrieval_report(self, k: int = 2) -> dict:
        """Context Recall: acerto dos casos-ouro + rejeição de off-topic (pegou o chunk certo?)."""
        hits, misses = 0, []
        for q, expected, domains in GOLDEN_RETRIEVAL:
            fontes = " ".join(h["source"] for h in self.kb.retrieve(q, k=k, domains=domains))
            if expected in fontes:
                hits += 1
            else:
                misses.append({"query": q, "expected": expected, "got": fontes or "—"})
        return {
            "hit_rate": round(hits / len(GOLDEN_RETRIEVAL), 3),
            "hits": hits, "total": len(GOLDEN_RETRIEVAL),
            "offtopic_rejected": self.kb.retrieve(OFFTOPIC_QUERY, k=k) == [],
            "misses": misses,
        }

    def context_precision(self, k: int = 2) -> dict:
        """Context Precision: fração dos k chunks recuperados que são da fonte esperada.
        Complementa o hit-rate (que só mede SE achou, não QUANTO ruído veio junto)."""
        per_query = []
        for q, expected, domains in GOLDEN_RETRIEVAL:
            hits = self.kb.retrieve(q, k=k, domains=domains)
            relevant = sum(1 for h in hits if expected in h["source"])
            per_query.append(relevant / k if hits else 0.0)
        return {"context_precision": round(sum(per_query) / len(per_query), 3),
                "per_query": per_query}

    @staticmethod
    def _avg(values: list):
        """Média ignorando None (o juiz pode falhar parse num caso)."""
        vals = [v for v in values if v is not None]
        return round(sum(vals) / len(vals), 3) if vals else None


class LLMJudge:
    """LLM-as-judge: pontua qualidades SUBJETIVAS que a régua determinística não pega
    (acionabilidade + aterramento + relevância). Genérico: julga (fatos, texto gerado).

    Caveat honesto: juiz LLM é ruidoso e enviesado (e aqui o Qwen julga a si mesmo — ideal
    seria um modelo mais forte/diferente). Use como sinal de tendência. Temperatura 0.
    """

    # Rubrica CALIBRADA contra notas humanas (severo). Padrão: rigor por dentro, DIDÁTICO ao falar.
    RUBRICA = (
        "Voce e um avaliador SEVERO de feedback de coach esportivo. Pontue o VEREDITO de 0.0 a "
        "1.0 em tres criterios:\n"
        "- acionabilidade: SO e alta (>= 0.7) se da um passo CONCRETO E ESPECIFICO e EXPLICA o "
        "porque de forma didatica, ligada ao dado/ciencia (ex: 'sua cadencia caiu 5% no fim = "
        "fadiga; faca 4 tiros de 1min focando passos curtos e rapidos, que reduzem o impacto'). "
        "Platitude generica ('mantenha a cadencia', 'monitore a carga', 'continue assim') NAO "
        "ensina nem orienta -> 0.0 a 0.2. Despejar numero/jargao sem explicar tambem nao.\n"
        "- aterramento: comeca em 1.0 e CAI a cada afirmacao que nao esteja LITERALMENTE nos dados. "
        "Citar causa nao medida (desidratacao, calor, deplecao de glicogenio) sem dado que sustente, "
        "ou interpretar mal um numero, derruba para <= 0.4.\n"
        "- relevancia: o veredito ENDERECA a situacao real (o que aconteceu, o risco, a duvida "
        "implicita nos dados)? Resposta generica que serviria pra qualquer caso = 0.0 a 0.3, mesmo "
        "que bem fundamentada. Resposta sobre algo fora do que os dados mostram = 0.0.\n"
        "EXEMPLOS de nota:\n"
        "- 'Mantenha a cadencia e monitore a carga semanal' -> acionabilidade 0.1 (generico, nao ensina).\n"
        "- 'A FC subiu na 2a metade, pode ser desidratacao' sem dado de hidratacao/calor -> aterramento 0.3.\n"
        "Responda APENAS um JSON valido, sem texto fora dele:\n"
        '{"acionabilidade": 0.0, "aterramento": 0.0, "relevancia": 0.0, "justificativa": "uma frase curta"}'
    )

    def __init__(self, llm):
        self.llm = llm

    @staticmethod
    def _parse(raw: str) -> dict:
        """Extrai o 1o objeto JSON da resposta (robusto a texto em volta)."""
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return {"acionabilidade": None, "aterramento": None, "relevancia": None,
                    "justificativa": "parse falhou"}
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"acionabilidade": None, "aterramento": None, "relevancia": None,
                    "justificativa": "json invalido"}
        return {
            "acionabilidade": data.get("acionabilidade"),
            "aterramento": data.get("aterramento"),
            "relevancia": data.get("relevancia"),
            "justificativa": data.get("justificativa", ""),
        }

    def judge(self, facts: str, verdict: str) -> dict:
        prompt = f"DADOS FORNECIDOS:\n{facts}\n\nTEXTO A AVALIAR:\n{verdict}"
        return self._parse(self.llm.chat(self.RUBRICA, prompt))
