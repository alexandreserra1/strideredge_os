"""analytics/coach_eval.py — eval anti-alucinação do coach.

Mede, de forma DETERMINÍSTICA, se o veredito é fiel ao que foi fornecido:
- numeric_fidelity: fração dos números do veredito que aparecem no prompt.
  (pega número inventado E conta feita pelo LLM — princípio "conclusão pronta".)
- citation_validity: fração das fontes citadas (PMCxxxx) presentes nas evidências.

evaluate() roda o coach numa atividade e devolve as métricas + o veredito.
"""

import json
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

    # Causas que NUNCA medimos: se aparecem no veredito, e extrapolacao (alucinacao de contexto).
    EXTRAPOLATION_TERMS = ("desidrat", "calor", "glicog", "clima")

    @classmethod
    def extrapolation_terms(cls, verdict: str) -> list:
        """Termos de causa NAO medida presentes no veredito (guard deterministico de aterramento)."""
        v = verdict.lower()
        return [t for t in cls.EXTRAPOLATION_TERMS if t in v]

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
            "prompt": prompt,   # o LLM-judge precisa dos fatos p/ avaliar aterramento
        }


class LLMJudge:
    """LLM-as-judge: pontua qualidades SUBJETIVAS que a regua deterministica nao pega
    (acionabilidade + aterramento ao contexto). Complementa o CoachEvaluator.

    Caveat honesto: juiz LLM e ruidoso e enviesado (e aqui o Qwen julga a si mesmo —
    ideal seria um modelo mais forte/diferente). Use como sinal de tendencia, nao verdade
    absoluta. Roda em temperatura 0 para consistencia.
    """

    # Rubrica CALIBRADA contra notas humanas do atleta (severo). O juiz cru era leniente
    # (MAE ~0.65 vs humano). Padrao do coach: rigor por dentro, DIDATICO ao falar com o atleta.
    RUBRICA = (
        "Voce e um avaliador SEVERO de feedback de coach esportivo. Pontue o VEREDITO de 0.0 a "
        "1.0 em dois criterios:\n"
        "- acionabilidade: SO e alta (>= 0.7) se da um passo CONCRETO E ESPECIFICO e EXPLICA o "
        "porque de forma didatica, ligada ao dado/ciencia (ex: 'sua cadencia caiu 5% no fim = "
        "fadiga; faca 4 tiros de 1min focando passos curtos e rapidos, que reduzem o impacto'). "
        "Platitude generica ('mantenha a cadencia', 'monitore a carga', 'continue assim') NAO "
        "ensina nem orienta -> 0.0 a 0.2. Despejar numero/jargao sem explicar tambem nao.\n"
        "- aterramento: comeca em 1.0 e CAI a cada afirmacao que nao esteja LITERALMENTE nos dados. "
        "Citar causa nao medida (desidratacao, calor, deplecao de glicogenio) sem dado que sustente, "
        "ou interpretar mal um numero, derruba para <= 0.4.\n"
        "EXEMPLOS de nota:\n"
        "- 'Mantenha a cadencia e monitore a carga semanal' -> acionabilidade 0.1 (generico, nao ensina).\n"
        "- 'A FC subiu na 2a metade, pode ser desidratacao' sem dado de hidratacao/calor -> aterramento 0.3.\n"
        "Responda APENAS um JSON valido, sem texto fora dele:\n"
        '{"acionabilidade": 0.0, "aterramento": 0.0, "justificativa": "uma frase curta"}'
    )

    def __init__(self, llm):
        self.llm = llm

    @staticmethod
    def _parse(raw: str) -> dict:
        """Extrai o 1o objeto JSON da resposta (robusto a texto em volta)."""
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return {"acionabilidade": None, "aterramento": None, "justificativa": "parse falhou"}
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"acionabilidade": None, "aterramento": None, "justificativa": "json invalido"}
        return {
            "acionabilidade": data.get("acionabilidade"),
            "aterramento": data.get("aterramento"),
            "justificativa": data.get("justificativa", ""),
        }

    def judge(self, facts: str, verdict: str) -> dict:
        prompt = f"DADOS FORNECIDOS AO COACH:\n{facts}\n\nVEREDITO DO COACH:\n{verdict}"
        return self._parse(self.llm.chat(self.RUBRICA, prompt))


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

    @staticmethod
    def _avg(values: list):
        """Media ignorando None (juiz pode falhar parse num caso)."""
        vals = [v for v in values if v is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    def coach_report(self, activity_ids: list, judge: "LLMJudge" = None) -> dict:
        """Fidelidade (deterministica) + acionabilidade/aterramento (LLM-judge, se fornecido)."""
        rows = [self.evaluator.evaluate(aid) for aid in activity_ids]
        n = max(len(rows), 1)
        out = {
            "n": len(rows),
            "numeric_fidelity": round(sum(r["numeric_fidelity"] for r in rows) / n, 3),
            "citation_validity": round(sum(r["citation_validity"] for r in rows) / n, 3),
        }
        if judge is not None:
            judged = [judge.judge(r["prompt"], r["verdict"]) for r in rows]
            out["acionabilidade"] = self._avg([j["acionabilidade"] for j in judged])
            out["aterramento"] = self._avg([j["aterramento"] for j in judged])
        return out

    def run(self, activity_ids: list, judge: "LLMJudge" = None) -> dict:
        return {"retrieval": self.retrieval_report(),
                "coach": self.coach_report(activity_ids, judge)}

    def calibrate(self, judge: "LLMJudge", labeled: list) -> dict:
        """Compara o juiz com NOTAS HUMANAS (gold) e calcula o erro medio absoluto (MAE).

        labeled: [(activity_id, acionabilidade_humana, aterramento_humano), ...].
        MAE alto = juiz desalinhado do humano (recalibrar a rubrica). Calibracao em poucas
        amostras e so indicativa; o ideal sao ~10-20 vereditos rotulados.
        """
        rows = []
        for aid, ha, hg in labeled:
            e = self.evaluator.evaluate(aid)
            j = judge.judge(e["prompt"], e["verdict"])
            rows.append({"acion_j": j["acionabilidade"], "acion_h": ha,
                         "ground_j": j["aterramento"], "ground_h": hg, "just": j["justificativa"]})

        def mae(jk, hk):
            ds = [abs(r[jk] - r[hk]) for r in rows if r[jk] is not None]
            return round(sum(ds) / len(ds), 3) if ds else None

        return {"rows": rows,
                "mae_acionabilidade": mae("acion_j", "acion_h"),
                "mae_aterramento": mae("ground_j", "ground_h")}


if __name__ == "__main__":
    from core.database import get_connection
    from api.deps import build_coach  # reusa a fiacao do coach (LLM + RAG + web)
    from analytics.coach import OllamaClient

    runs = [str(r[0]) for r in get_connection().execute(
        "SELECT activity_id FROM dim_activities WHERE primary_type='RUN' ORDER BY start_time DESC LIMIT 4"
    ).fetchall()]

    judge = LLMJudge(OllamaClient(temperature=0))           # juiz deterministico
    report = Benchmark(build_coach(temperature=0)).run(runs, judge=judge)
    r, c = report["retrieval"], report["coach"]
    print("=== BOLETIM DO COACH ===")
    print(f"RAG  retrieval hit-rate : {r['hit_rate']:.0%} ({r['hits']}/{r['total']})  "
          f"off-topic rejeitado: {r['offtopic_rejected']}")
    for m in r["misses"]:
        print(f"     MISS: '{m['query']}' -> esperava {m['expected']}, veio {m['got']}")
    print(f"Deterministico  fidelidade numerica: {c['numeric_fidelity']:.0%}  "
          f"citacao: {c['citation_validity']:.0%}")
    print(f"LLM-judge       acionabilidade: {c.get('acionabilidade')}  "
          f"aterramento: {c.get('aterramento')}  (n={c['n']} treinos)")
