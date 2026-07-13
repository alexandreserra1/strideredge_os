"""Avaliação de RELEVÂNCIA do RAG com embeddings REAIS (bge-m3 via Ollama).

Verifica que cada pergunta recupera o chunk da fonte esperada — é o teste de
"as análises chegam boas" (o chunk certo aparece). Pula automaticamente se o
Ollama não estiver rodando. Requer a base já indexada (python -m rag.knowledge_base).
"""

import httpx
import pytest

from rag.knowledge_base import KnowledgeBase, OllamaEmbedder
from analytics.coach_eval import GOLDEN_RETRIEVAL, OFFTOPIC_QUERY, Benchmark


def _ollama_up() -> bool:
    try:
        httpx.get("http://localhost:11434/api/version", timeout=2.0)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ollama_up(), reason="Ollama não está rodando")


# Casos-ouro centralizados em analytics.coach_eval (mesma fonte do Benchmark — sem duplicar).
CASES = GOLDEN_RETRIEVAL


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(embedder=OllamaEmbedder())


@pytest.mark.parametrize("query,expected_source", CASES)
def test_retrieval_relevance(kb, query, expected_source):
    hits = kb.retrieve(query, k=2)
    assert hits, f"nada recuperado para: {query}"
    fontes = " ".join(h["source"] for h in hits)
    assert expected_source in fontes, f"esperava {expected_source} em '{query}', veio: {fontes}"


def test_offtopic_returns_nothing(kb):
    # pergunta sem relação com o corpus deve ficar abaixo do limiar
    assert kb.retrieve(OFFTOPIC_QUERY, k=2) == []


def test_context_precision_dentro_dos_limites(kb):
    # Benchmark so usa coach.knowledge -> stub minimo em vez de montar um Coach real
    fake_coach = type("FakeCoach", (), {"knowledge": kb})()
    report = Benchmark(fake_coach).context_precision(k=2)
    assert 0.0 <= report["context_precision"] <= 1.0
    assert len(report["per_query"]) == len(GOLDEN_RETRIEVAL)
