"""Testes herméticos do harness de avaliação do RAG (sem Ollama) — a ferramenta de medir
tem que ser confiável antes de confiarmos no boletim que ela produz."""

from analytics.rag_eval import RagBenchmark, LLMJudge, GOLDEN_RETRIEVAL


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, system, user):
        return self.reply


def test_llmjudge_parse_json_com_texto_em_volta():
    # LLM costuma cercar o JSON de texto — o parser tem que extrair mesmo assim
    judge = LLMJudge(_FakeLLM('Claro!\n{"acionabilidade": 0.8, "aterramento": 0.5, '
                              '"relevancia": 0.6, "justificativa": "extrapolou desidratacao"}\nFim.'))
    r = judge.judge("fatos", "veredito")
    assert r["acionabilidade"] == 0.8 and r["aterramento"] == 0.5 and r["relevancia"] == 0.6
    assert "desidrata" in r["justificativa"]


def test_llmjudge_resposta_invalida_nao_quebra():
    r = LLMJudge(_FakeLLM("desculpe, nao consigo")).judge("f", "v")
    assert r["acionabilidade"] is None and r["aterramento"] is None and r["relevancia"] is None


class _FakeKB:
    def __init__(self, mapping):
        self.mapping = mapping

    def retrieve(self, q, k=2):
        src = self.mapping.get(q)
        return [{"source": src}] if src else []


def test_benchmark_retrieval_report():
    first_q, first_src = GOLDEN_RETRIEVAL[0]
    bench = RagBenchmark(_FakeKB({first_q: first_src}))   # acerta só o 1º caso
    rep = bench.retrieval_report()
    assert rep["hits"] == 1 and rep["total"] == len(GOLDEN_RETRIEVAL)
    assert rep["offtopic_rejected"] is True               # off-topic não mapeado -> []
    assert rep["hit_rate"] == round(1 / len(GOLDEN_RETRIEVAL), 3)
    assert len(rep["misses"]) == len(GOLDEN_RETRIEVAL) - 1


def test_benchmark_context_precision():
    first_q, first_src = GOLDEN_RETRIEVAL[0]
    bench = RagBenchmark(_FakeKB({first_q: first_src}))
    rep = bench.context_precision(k=2)
    assert 0.0 <= rep["context_precision"] <= 1.0
    assert len(rep["per_query"]) == len(GOLDEN_RETRIEVAL)
