"""Avaliação de RELEVÂNCIA do RAG com embeddings REAIS (bge-m3 via Ollama).

Verifica que cada pergunta recupera o chunk da fonte esperada — é o teste de
"as análises chegam boas" (o chunk certo aparece). Pula automaticamente se o
Ollama não estiver rodando. Requer a base já indexada (python -m rag.knowledge_base).
"""

import httpx
import pytest

from rag.knowledge_base import KnowledgeBase, OllamaEmbedder


def _ollama_up() -> bool:
    try:
        httpx.get("http://localhost:11434/api/version", timeout=2.0)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ollama_up(), reason="Ollama não está rodando")


# (pergunta do atleta, trecho esperado na fonte) — palavras diferentes do corpus de propósito.
CASES = [
    ("minha passada esta lenta, risco de me machucar?", "PMC12440572"),   # cadência
    ("aumentei muito a carga essa semana, perigo?", "PMC7047972"),         # ACWR
    ("como distribuir intensidade dos treinos?", "PMC11679080"),           # polarizado
    ("estou quicando muito ao correr, gasto energia?", "PMC11127892"),     # economia/oscilação
    ("minha FC sobe sozinha no fim do treino longo", "PMC12271085"),       # deriva cardíaca
    ("quanto dormir para recuperar melhor?", "PMC10354314"),               # sono/recuperação
]


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
    assert kb.retrieve("qual a melhor receita de panqueca?", k=2) == []
