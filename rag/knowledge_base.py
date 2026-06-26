"""rag/knowledge_base.py — base de conhecimento para RAG (busca semantica).

Pecas:
  - OllamaEmbedder: texto -> vetor (implementa BaseEmbedder).
  - KnowledgeBase: guarda os chunks+vetores no DuckDB e busca os mais parecidos.
  - load_corpus: le o arquivo de fontes e separa cada chunk da sua FONTE (citacao).

Banco separado (storage/knowledge.db) para nao disputar lock com a telemetria.
"""

from pathlib import Path
from typing import List, Tuple

import duckdb
import httpx

from core.database import PROJECT_ROOT
from core.framework.interfaces import BaseEmbedder, BaseRetriever

EMBED_DIM = 1024  # dimensao do vetor do bge-m3 (multilingue, bom em portugues)
KNOWLEDGE_DB = PROJECT_ROOT / "storage" / "knowledge.db"


class OllamaEmbedder(BaseEmbedder):
    """Gera embeddings via Ollama. Padrao bge-m3 (multilingue, sem prefixos).

    doc_prefix/query_prefix existem para modelos que exigem prefixo de tarefa
    (ex: nomic usa 'search_document:' / 'search_query:'). bge-m3 nao usa.
    """

    def __init__(self, model: str = "bge-m3",
                 url: str = "http://localhost:11434/api/embeddings",
                 doc_prefix: str = "", query_prefix: str = ""):
        self.model = model
        self.url = url
        self.doc_prefix = doc_prefix
        self.query_prefix = query_prefix

    def embed(self, text: str) -> List[float]:
        r = httpx.post(self.url, json={"model": self.model, "prompt": text}, timeout=60.0)
        r.raise_for_status()
        return r.json()["embedding"]

    def embed_document(self, text: str) -> List[float]:
        return self.embed(self.doc_prefix + text)

    def embed_query(self, text: str) -> List[float]:
        return self.embed(self.query_prefix + text)


class KnowledgeBase(BaseRetriever):
    """Vector store curado sobre DuckDB. COMPOE um BaseEmbedder (injetado)."""

    def __init__(self, embedder: BaseEmbedder, db_path: Path = KNOWLEDGE_DB,
                 min_similarity: float = 0.52):  # calibrado: cobertos ~0.55+, off-topic <0.5
        self.embedder = embedder
        self.db_path = str(db_path)
        self.min_similarity = min_similarity
        con = duckdb.connect(self.db_path)
        con.execute(
            f"""CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id INTEGER, text VARCHAR, source VARCHAR,
                    embedding FLOAT[{EMBED_DIM}]
                )"""
        )
        con.close()

    def index(self, chunks: List[Tuple[str, str]]) -> int:
        """(Re)indexa do zero: embeda cada chunk e grava texto+fonte+vetor."""
        con = duckdb.connect(self.db_path)
        con.execute("DELETE FROM knowledge_chunks")
        for i, (text, source) in enumerate(chunks):
            emb = self.embedder.embed_document(text)  # o embedder cuida de prefixo, se houver
            con.execute(
                "INSERT INTO knowledge_chunks VALUES (?, ?, ?, ?)",
                [i, text, source, emb],
            )
        con.close()
        return len(chunks)

    def search(self, query: str, k: int = 4, min_similarity: float = 0.0) -> list:
        """Busca os k chunks mais proximos do sentido da pergunta.

        Usa array_cosine_similarity (nativo do DuckDB). min_similarity descarta
        trechos irrelevantes — a base do anti-alucinacao (so usa o que e relevante).
        """
        qvec = self.embedder.embed_query(query)  # o embedder aplica prefixo, se houver
        con = duckdb.connect(self.db_path, read_only=True)
        rows = con.execute(
            f"""SELECT text, source,
                       array_cosine_similarity(embedding, ?::FLOAT[{EMBED_DIM}]) AS sim
                FROM knowledge_chunks
                ORDER BY sim DESC
                LIMIT ?""",
            [qvec, k],
        ).fetchall()
        con.close()
        return [
            {"text": t, "source": s, "similarity": round(sim, 3)}
            for t, s, sim in rows
            if sim >= min_similarity
        ]

    def retrieve(self, query: str, k: int = 3) -> list:
        """Interface BaseRetriever: usa o limiar proprio e marca origem 'curado'."""
        hits = self.search(query, k=k, min_similarity=self.min_similarity)
        return [{"text": h["text"], "source": h["source"], "origin": "curado"} for h in hits]


def load_corpus(path: Path) -> List[Tuple[str, str]]:
    """Le um .md de fontes: chunks separados por '---', cada um com linha 'FONTE:'."""
    raw = Path(path).read_text(encoding="utf-8")
    chunks = []
    for block in raw.split("\n---\n"):
        block = block.strip()
        if not block:
            continue
        source = "desconhecida"
        text_lines = []
        for line in block.splitlines():
            if line.strip().upper().startswith("FONTE:"):
                source = line.split(":", 1)[1].strip()
            else:
                text_lines.append(line)
        text = " ".join(text_lines).strip()
        if text:
            chunks.append((text, source))
    return chunks


if __name__ == "__main__":
    # (Re)indexa o corpus. Rode apos adicionar/editar fontes em rag/sources/.
    kb = KnowledgeBase(embedder=OllamaEmbedder())
    n = kb.index(load_corpus(PROJECT_ROOT / "rag" / "sources" / "corpus.md"))
    print(f"Base de conhecimento (re)indexada: {n} chunks.")
