"""analytics/coach_eval.py — eval anti-alucinação do coach.

Mede, de forma DETERMINÍSTICA, se o veredito é fiel ao que foi fornecido:
- numeric_fidelity: fração dos números do veredito que aparecem no prompt.
  (pega número inventado E conta feita pelo LLM — princípio "conclusão pronta".)
- citation_validity: fração das fontes citadas (PMCxxxx) presentes nas evidências.

evaluate() roda o coach numa atividade e devolve as métricas + o veredito.
"""

import re

from analytics.coach import Coach


class CoachEvaluator:
    """Avalia a fidelidade do veredito ao prompt (dados + evidências)."""

    def __init__(self, coach: Coach):
        self.coach = coach

    @staticmethod
    def _numbers(text: str) -> set:
        # aceita virgula OU ponto decimal (PT usa virgula) e normaliza p/ comparar:
        # '2,9' (veredito) e '2.9' (prompt) viram o MESMO token. Sem isso, a virgula
        # quebra '2,9' em '2' e '9' -> falso "numero inventado".
        return {m.replace(",", ".") for m in re.findall(r"\d+(?:[.,]\d+)?", text)}

    @staticmethod
    def _citations(text: str) -> set:
        return set(m.upper() for m in re.findall(r"PMC\d+", text, re.IGNORECASE))

    def numeric_fidelity(self, verdict: str, prompt: str) -> float:
        nums = self._numbers(verdict)
        if not nums:
            return 1.0
        supported = nums & self._numbers(prompt)
        return round(len(supported) / len(nums), 3)

    def citation_validity(self, verdict: str, prompt: str) -> float:
        cited = self._citations(verdict)
        if not cited:
            return 1.0
        valid = cited & self._citations(prompt)
        return round(len(valid) / len(cited), 3)

    def evaluate(self, activity_id: str) -> dict:
        """Gera o veredito sobre o MESMO prompt e mede a fidelidade."""
        prompt = self.coach.build_user_prompt(activity_id)
        verdict = self.coach.llm.chat(self.coach.SYSTEM_PROMPT, prompt)
        return {
            "numeric_fidelity": self.numeric_fidelity(verdict, prompt),
            "citation_validity": self.citation_validity(verdict, prompt),
            "verdict": verdict,
        }


# Casos-ouro de retrieval (pergunta do atleta -> fonte esperada). FONTE UNICA:
# o test_rag_eval.py importa daqui (antes estavam duplicados no teste).
GOLDEN_RETRIEVAL = [
    ("minha passada esta lenta, risco de me machucar?", "PMC12440572"),   # cadencia
    ("aumentei muito a carga essa semana, perigo?", "PMC7047972"),         # ACWR
    ("como distribuir intensidade dos treinos?", "PMC11679080"),           # polarizado
    ("estou quicando muito ao correr, gasto energia?", "PMC11127892"),     # economia/oscilacao
    ("minha FC sobe sozinha no fim do treino longo", "PMC12271085"),       # deriva cardiaca
    ("quanto dormir para recuperar melhor?", "PMC10354314"),               # sono/recuperacao
    ("qual o jeito certo de construir base aerobica devagar?", "PMC11986187"),  # zona 2
    ("musculacao ajuda a correr melhor?", "PMC11052887"),                  # forca x economia
    ("quanto comer de acucar numa prova longa?", "PMC4008807"),            # fueling carboidrato
    ("treinar no calor atrapalha? da pra me adaptar?", "PMC6890862"),      # calor/aclimatacao
]
OFFTOPIC_QUERY = "qual a melhor receita de panqueca?"


class Benchmark:
    """Boletim de qualidade (coach + RAG). 'Eval-driven': mede ANTES de mexer no prompt/corpus.

    Reusa o CoachEvaluator (fidelidade) e o proprio retriever do coach (retrieval). Roda com
    Ollama de pe — e a ferramenta de medicao para iterar prompt/RAG sem achismo.
    """

    def __init__(self, coach):
        self.coach = coach
        self.evaluator = CoachEvaluator(coach)

    def retrieval_report(self, k: int = 2) -> dict:
        """Acerto dos casos-ouro + rejeicao de off-topic (o RAG 'pega' o chunk certo?)."""
        kb = self.coach.knowledge
        hits, misses = 0, []
        for q, expected in GOLDEN_RETRIEVAL:
            fontes = " ".join(h["source"] for h in kb.retrieve(q, k=k))
            if expected in fontes:
                hits += 1
            else:
                misses.append({"query": q, "expected": expected, "got": fontes or "—"})
        return {
            "hit_rate": round(hits / len(GOLDEN_RETRIEVAL), 3),
            "hits": hits, "total": len(GOLDEN_RETRIEVAL),
            "offtopic_rejected": kb.retrieve(OFFTOPIC_QUERY, k=k) == [],
            "misses": misses,
        }

    def coach_report(self, activity_ids: list) -> dict:
        """Fidelidade media (numeros + citacoes) do veredito sobre varias atividades."""
        rows = [self.evaluator.evaluate(aid) for aid in activity_ids]
        n = max(len(rows), 1)
        return {
            "n": len(rows),
            "numeric_fidelity": round(sum(r["numeric_fidelity"] for r in rows) / n, 3),
            "citation_validity": round(sum(r["citation_validity"] for r in rows) / n, 3),
        }

    def run(self, activity_ids: list) -> dict:
        return {"retrieval": self.retrieval_report(), "coach": self.coach_report(activity_ids)}


if __name__ == "__main__":
    from core.database import get_connection
    from api.deps import build_coach  # reusa a fiacao do coach (LLM + RAG + web)

    runs = [str(r[0]) for r in get_connection().execute(
        "SELECT activity_id FROM dim_activities WHERE primary_type='RUN' ORDER BY start_time DESC LIMIT 4"
    ).fetchall()]

    report = Benchmark(build_coach(temperature=0)).run(runs)  # temp 0 = medicao deterministica
    r, c = report["retrieval"], report["coach"]
    print("=== BOLETIM DO COACH (baseline) ===")
    print(f"RAG  retrieval hit-rate : {r['hit_rate']:.0%} ({r['hits']}/{r['total']})  "
          f"off-topic rejeitado: {r['offtopic_rejected']}")
    for m in r["misses"]:
        print(f"     MISS: '{m['query']}' -> esperava {m['expected']}, veio {m['got']}")
    print(f"Coach fidelidade numerica: {c['numeric_fidelity']:.0%}  "
          f"validade de citacao: {c['citation_validity']:.0%}  (n={c['n']} treinos)")
