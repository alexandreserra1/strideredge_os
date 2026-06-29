"""Testes herméticos do harness de avaliação (sem Ollama) — a ferramenta de medir
tem que ser confiável antes de confiarmos no boletim que ela produz."""

from analytics.coach_eval import CoachEvaluator, Benchmark, GOLDEN_RETRIEVAL


def test_numeric_fidelity_pega_numero_inventado():
    ev = CoachEvaluator(coach=None)  # scoring é puro, não usa o coach
    # 5.5 está no prompt, 9.9 não -> metade suportada (pega conta/numero inventado)
    assert ev.numeric_fidelity("pace 5.5 e carga 9.9", "seu pace foi 5.5") == 0.5
    assert ev.numeric_fidelity("sem numeros", "prompt 5.5") == 1.0


def test_numeric_fidelity_virgula_decimal_pt():
    ev = CoachEvaluator(coach=None)
    # veredito em PT (virgula) vs prompt com ponto: deve casar -> 1.0 (sem falso negativo)
    assert ev.numeric_fidelity("desacoplamento de 2,9% e ACWR 0,96", "decoupling 2.9 acwr 0.96") == 1.0


def test_citation_validity():
    ev = CoachEvaluator(coach=None)
    assert ev.citation_validity("fontes PMC123 e PMC999", "evidencia PMC123") == 0.5
    assert ev.citation_validity("sem citacao", "PMC123") == 1.0


class _FakeKB:
    def __init__(self, mapping):
        self.mapping = mapping

    def retrieve(self, q, k=2):
        src = self.mapping.get(q)
        return [{"source": src}] if src else []


class _FakeCoach:
    def __init__(self, kb):
        self.knowledge = kb


def test_benchmark_retrieval_report():
    first_q, first_src = GOLDEN_RETRIEVAL[0]
    bench = Benchmark(_FakeCoach(_FakeKB({first_q: first_src})))  # acerta só o 1º caso
    rep = bench.retrieval_report()
    assert rep["hits"] == 1 and rep["total"] == len(GOLDEN_RETRIEVAL)
    assert rep["offtopic_rejected"] is True  # off-topic não mapeado -> []
    assert rep["hit_rate"] == round(1 / len(GOLDEN_RETRIEVAL), 3)
    assert len(rep["misses"]) == len(GOLDEN_RETRIEVAL) - 1
