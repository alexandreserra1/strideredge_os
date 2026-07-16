"""Testes UNIT do RAG (mecânica), com embedder mockado — rápido, sem Ollama.

FakeEmbedder gera vetores one-hot por palavra-chave: textos do mesmo tema ficam
idênticos (cosine 1.0) e de temas diferentes ficam ortogonais (cosine 0.0). Isso
deixa a ordenação e o limiar totalmente determinísticos e testáveis.
"""

import duckdb
import pytest

from core.framework.interfaces import BaseEmbedder
from rag.contextualize import ContextGenerator
from rag.knowledge_base import KnowledgeBase, load_corpus

EMBED_DIM = 1024
TOPICS = ["cadencia", "carga", "intensidade", "oscilacao"]


class FakeEmbedder(BaseEmbedder):
    def embed(self, text: str):
        v = [0.0] * EMBED_DIM
        low = text.lower()
        for i, kw in enumerate(TOPICS):
            if kw in low:
                v[i] = 1.0
                return v
        v[EMBED_DIM - 1] = 1.0  # bucket "off-topic"
        return v


@pytest.fixture
def kb(tmp_path):
    base = KnowledgeBase(embedder=FakeEmbedder(), db_path=tmp_path / "k.db", min_similarity=0.52)
    base.index([
        ("A cadencia ideal de corrida fica entre 170 e 180.", "FonteCadencia"),
        ("A carga aguda cronica acima de 1.5 eleva o risco.", "FonteCarga"),
        ("A intensidade polarizada usa 80 por cento leve.", "FonteIntensidade"),
    ])
    return base


def test_index_returns_count(tmp_path):
    base = KnowledgeBase(embedder=FakeEmbedder(), db_path=tmp_path / "k.db")
    n = base.index([("texto sobre cadencia", "F1"), ("texto sobre carga", "F2")])
    assert n == 2


def test_search_top_is_relevant(kb):
    hits = kb.search("como melhorar minha cadencia", k=3)
    assert hits[0]["source"] == "FonteCadencia"
    assert hits[0]["similarity"] == pytest.approx(1.0, abs=1e-6)


def test_retrieve_filters_offtopic(kb):
    # 'panqueca' não casa com nenhum tema -> cosine 0 -> abaixo do limiar -> vazio
    assert kb.retrieve("receita de panqueca", k=3) == []


def test_retrieve_marks_origin_curado(kb):
    hits = kb.retrieve("intensidade dos treinos", k=3)
    assert hits and all(h["origin"] == "curado" for h in hits)


def test_search_respects_k(kb):
    assert len(kb.search("carga de treino", k=1)) == 1


def test_load_corpus_parses_text_and_source(tmp_path):
    path = tmp_path / "corpus.md"
    path.write_text(
        "Primeiro trecho de teste.\nFONTE: Fonte A\n"
        "\n---\n"
        "Segundo trecho de teste.\nFONTE: Fonte B\n",
        encoding="utf-8",
    )
    chunks = load_corpus(path)
    assert chunks == [
        ("Primeiro trecho de teste.", "Fonte A"),
        ("Segundo trecho de teste.", "Fonte B"),
    ]


# ---------- Contextual Retrieval (rag/contextualize.py) ----------

class _FakeLLM:
    def __init__(self, reply="contexto fake", raise_it=False):
        self.reply, self.raise_it = reply, raise_it

    def chat(self, system_prompt, user_prompt):
        if self.raise_it:
            raise RuntimeError("llm off")
        return self.reply


def _search_text_row(base, chunk_id=0):
    con = duckdb.connect(base.db_path, read_only=True)
    row = con.execute("SELECT text, search_text FROM knowledge_chunks WHERE id = ?",
                      [chunk_id]).fetchone()
    con.close()
    return row


def test_index_sem_context_gen_mantem_search_text_igual_ao_text(tmp_path):
    base = KnowledgeBase(embedder=FakeEmbedder(), db_path=tmp_path / "k.db")
    base.index([("texto sobre cadencia", "F1")])
    text, search_text = _search_text_row(base)
    assert text == search_text == "texto sobre cadencia"


def test_index_com_context_gen_nao_altera_text_so_search_text(tmp_path):
    base = KnowledgeBase(embedder=FakeEmbedder(), db_path=tmp_path / "k.db")
    ctx_gen = ContextGenerator(_FakeLLM(reply="Estudo sobre cadencia e lesao."))
    base.index([("cadencia alta reduz impacto", "PMC1")], context_gen=ctx_gen)

    text, search_text = _search_text_row(base)
    assert text == "cadencia alta reduz impacto"           # puro — o que vai pra citacao/UI
    assert "Estudo sobre cadencia e lesao." in search_text  # contexto entrou so no search_text
    assert "cadencia alta reduz impacto" in search_text


def test_context_generator_degrada_gracioso_se_llm_falha(tmp_path):
    base = KnowledgeBase(embedder=FakeEmbedder(), db_path=tmp_path / "k.db")
    ctx_gen = ContextGenerator(_FakeLLM(raise_it=True))
    base.index([("cadencia alta reduz impacto", "PMC1")], context_gen=ctx_gen)  # nao levanta

    text, search_text = _search_text_row(base)
    assert text == search_text == "cadencia alta reduz impacto"  # sem contexto
