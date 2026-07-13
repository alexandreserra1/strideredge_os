"""Testa o reranking (rag/rerank.py) com fakes — sem tocar o Ollama."""

from core.framework.interfaces import BaseLLMClient, BaseRetriever
from rag.rerank import LLMReranker, RerankedRetriever


class _FakeLLM(BaseLLMClient):
    def __init__(self, reply="", raise_it=False):
        self.reply, self.raise_it = reply, raise_it

    def chat(self, system_prompt, user_prompt):
        if self.raise_it:
            raise RuntimeError("llm off")
        return self.reply

    def chat_stream(self, system_prompt, user_prompt):
        yield self.reply


class _FakeBase(BaseRetriever):
    def __init__(self, docs):
        self.docs = docs

    def retrieve(self, query, k=3):
        return self.docs[:k]


def _docs(n):
    return [{"text": f"trecho {i}", "source": f"S{i}", "origin": "curado"} for i in range(n)]


def test_reranker_reordena_pela_resposta_do_llm():
    cands = _docs(4)
    r = LLMReranker(_FakeLLM(reply="2, 0, 1, 3"))
    out = r.rerank("q", cands, top_k=2)
    assert [c["source"] for c in out] == ["S2", "S0"]  # LLM pôs o 2 e o 0 na frente


def test_reranker_completa_os_esquecidos():
    # LLM só citou 2 dos 4 -> os outros seguem no fim, na ordem original
    r = LLMReranker(_FakeLLM(reply="3,1"))
    out = r.rerank("q", _docs(4), top_k=4)
    assert [c["source"] for c in out] == ["S3", "S1", "S0", "S2"]


def test_reranker_degrada_gracioso_se_llm_falha():
    r = LLMReranker(_FakeLLM(raise_it=True))
    out = r.rerank("q", _docs(3), top_k=2)
    assert [c["source"] for c in out] == ["S0", "S1"]  # ordem original do retriever


def test_reranked_retriever_busca_N_reordena_devolve_k():
    base = _FakeBase(_docs(8))
    rr = RerankedRetriever(base, LLMReranker(_FakeLLM(reply="5,4")), fetch_k=8)
    out = rr.retrieve("q", k=2)
    assert [c["source"] for c in out] == ["S5", "S4"]


def test_reranked_retriever_base_vazia_devolve_vazio():
    # base vazia (off-topic barrado pelo piso) -> nada, sem chamar o LLM
    rr = RerankedRetriever(_FakeBase([]), LLMReranker(_FakeLLM(raise_it=True)), fetch_k=8)
    assert rr.retrieve("panqueca", k=3) == []


def test_reranker_cache_nao_rechama_o_llm():
    calls = {"n": 0}

    class _Counting(_FakeLLM):
        def chat(self, system_prompt, user_prompt):
            calls["n"] += 1
            return "1,0"

    r = LLMReranker(_Counting())
    cands = _docs(3)
    a = r.rerank("q", cands, top_k=2)
    b = r.rerank("q", cands, top_k=2)   # mesma pergunta+candidatos -> cache hit
    assert calls["n"] == 1              # LLM chamado uma vez só
    assert a == b
