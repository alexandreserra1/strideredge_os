"""rag/rerank.py — reranking dos candidatos do RAG (precisão > o bi-encoder).

O retriever (embeddings + BM25) é rápido mas troca precisão por velocidade: devolve um
top-N generoso. O RERANKER olha cada candidato JUNTO com a pergunta (estilo cross-encoder) e
reordena, deixando os de fato mais relevantes no topo. Aqui o "cross-encoder" é o LLM local
(Qwen) — sem dependência nova (torch/sentence-transformers), 100% local, on-brand.

Composição (constituição): `RerankedRetriever` embrulha QUALQUER BaseRetriever + um reranker.
Degrada gracioso: base vazia -> vazio; LLM ilegível -> mantém a ordem do retriever.
"""

import re
from typing import List

from core.framework.interfaces import BaseLLMClient, BaseRetriever

_SYSTEM = (
    "Voce classifica trechos por RELEVANCIA a uma pergunta. Responda SOMENTE com os numeros "
    "dos trechos, do MAIS relevante ao menos, separados por virgula (ex: 2,0,3). Nada de texto."
)


class LLMReranker:
    """Reordena candidatos usando o LLM local como juiz de relevância (cross-encoder-like).

    Tem CACHE em memória: (pergunta + candidatos + k) -> ordem. Como a chamada ao LLM é o
    custo, repetir a mesma recuperação não paga de novo. Precisa ser SINGLETON pra o cache
    persistir entre requests (ver api/deps._reranked_knowledge)."""

    def __init__(self, llm: BaseLLMClient, cache_size: int = 256):
        self.llm = llm
        self.cache_size = cache_size
        self._cache: dict = {}   # ordenado por inserção -> evicção FIFO do mais antigo

    def rerank(self, query: str, candidates: List[dict], top_k: int) -> List[dict]:
        if len(candidates) <= 1:
            return candidates[:top_k]
        # os textos identificam os candidatos (fonte pode repetir entre chunks do mesmo PMC)
        key = (query, tuple(c["text"] for c in candidates), top_k)
        if key in self._cache:
            return self._cache[key]

        listing = "\n".join(f"[{i}] {c['text'][:160]}" for i, c in enumerate(candidates))
        user = f"Pergunta: {query}\n\nTrechos:\n{listing}\n\nOrdem (mais relevante primeiro):"
        try:
            out = self.llm.chat(_SYSTEM, user)
            order, seen = [], set()
            for n in re.findall(r"\d+", out):
                i = int(n)
                if i < len(candidates) and i not in seen:
                    order.append(i)
                    seen.add(i)
            # ordem do LLM + o que ele esqueceu (mantém no fim, na ordem original)
            ranked = [candidates[i] for i in order]
            ranked += [c for j, c in enumerate(candidates) if j not in seen]
            ranked = ranked[:top_k]
        except Exception:
            return candidates[:top_k]   # LLM fora do ar / resposta ruim -> ordem do retriever

        if len(self._cache) >= self.cache_size:
            self._cache.pop(next(iter(self._cache)))   # evicta o mais antigo (FIFO)
        self._cache[key] = ranked
        return ranked


class RerankedRetriever(BaseRetriever):
    """Compõe um retriever base + reranker: busca `fetch_k` candidatos, reordena, devolve k.

    Como o base já aplicou o piso de relevância (anti-alucinação), o reranker só REORDENA —
    nunca introduz off-topic. Se o base devolve [], o resultado é [] (segurança preservada)."""

    def __init__(self, base: BaseRetriever, reranker: LLMReranker, fetch_k: int = 8):
        self.base = base
        self.reranker = reranker
        self.fetch_k = fetch_k

    def retrieve(self, query: str, k: int = 3) -> list:
        candidates = self.base.retrieve(query, k=max(self.fetch_k, k))
        return self.reranker.rerank(query, candidates, k)
