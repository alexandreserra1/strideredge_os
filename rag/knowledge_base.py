"""rag/knowledge_base.py — base de conhecimento para RAG (busca semantica).

Pecas:
  - OllamaEmbedder: texto -> vetor (implementa BaseEmbedder).
  - KnowledgeBase: guarda os chunks+vetores no DuckDB e busca os mais parecidos.
  - load_corpus: le o arquivo de fontes e separa cada chunk da sua FONTE (citacao).

Banco separado (storage/knowledge.db) para nao disputar lock com a telemetria.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional, Tuple

import duckdb
import httpx

from core.database import PROJECT_ROOT
from core.framework.interfaces import BaseEmbedder, BaseRetriever
from rag.contextualize import ContextGenerator

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
                    id INTEGER, text VARCHAR, source VARCHAR, search_text VARCHAR,
                    embedding FLOAT[{EMBED_DIM}], domain VARCHAR DEFAULT 'geral'
                )"""
        )
        con.close()

    def index(self, chunks: List[Tuple], context_gen: ContextGenerator = None) -> int:
        """(Re)indexa do zero: embeda cada chunk, grava texto+fonte+vetor e cria o
        indice FTS (BM25) do DuckDB sobre o texto — pra busca hibrida (denso+palavra).

        context_gen (opcional): Contextual Retrieval (Anthropic) — gera uma frase de contexto
        por chunk e usa CONTEXTO+TEXTO so no indice BM25 (search_text). O DENSO continua
        embedando o `text` PURO: testado empiricamente, prefixar contexto ao texto ANTES de
        embedar dilui termos-ancora do chunk (ex: query usa 'quicando', o texto tem 'quicar',
        o contexto parafraseia pra 'oscilacao vertical' — a media do embedding se afasta do
        termo exato que o denso pegava bem). BM25 nao sofre desse efeito (so soma vocabulario
        novo ao indice invertido), entao e onde o contexto realmente ajuda."""
        con = duckdb.connect(self.db_path)
        con.execute("DELETE FROM knowledge_chunks")
        for i, chunk in enumerate(chunks):
            text, source = chunk[0], chunk[1]
            domain = chunk[2] if len(chunk) > 2 else "geral"   # retrocompat: 2-tupla vira 'geral'
            ctx = context_gen.generate(text, source) if context_gen else ""
            search_text = f"{ctx}\n\n{text}".strip() if ctx else text
            emb = self.embedder.embed_document(text)  # denso: SEMPRE do texto puro
            con.execute(
                "INSERT INTO knowledge_chunks VALUES (?, ?, ?, ?, ?, ?)",
                [i, text, source, search_text, emb, domain],
            )
        try:  # indice de texto (BM25). Se o extension nao instalar (sem rede), segue so denso.
            con.execute("INSTALL fts; LOAD fts;")
            con.execute(  # indexa search_text (contexto+texto) E fonte — pra achar tambem
                "PRAGMA create_fts_index('knowledge_chunks', 'id', 'search_text', 'source', "
                "stemmer='portuguese', overwrite=1)"
            )
        except Exception:
            pass
        con.close()
        return len(chunks)

    def _bm25(self, con, query: str) -> dict:
        """Ranking BM25 (palavra-chave) via FTS do DuckDB. id -> posicao (1 = melhor).
        Vazio se o FTS nao estiver disponivel (fallback gracioso pra busca so-densa)."""
        try:
            con.execute("LOAD fts;")
            rows = con.execute(
                """SELECT id, fts_main_knowledge_chunks.match_bm25(id, ?) AS score
                   FROM knowledge_chunks
                   WHERE score IS NOT NULL
                   ORDER BY score DESC""",
                [query],
            ).fetchall()
            return {rid: rank for rank, (rid, _s) in enumerate(rows, 1)}
        except Exception:
            return {}

    def search(self, query: str, k: int = 4, min_similarity: float = 0.0,
               domains: "Optional[List[str]]" = None) -> list:
        """Busca HIBRIDA: funde o ranking SEMANTICO (embeddings, array_cosine_similarity)
        com o de PALAVRA-CHAVE (BM25/FTS). O denso e o PISO de relevancia (min_similarity) —
        base do anti-alucinacao; o BM25 so reordena (termos exatos: 'ACWR', 'PMCxxxx').

        `domains`: se dado, ROTEIA a busca so pra esses dominios (WHERE domain IN ...) — evita
        bleed (query de cadencia puxar chunk de tenis). None = todo o corpus (retrocompativel)."""
        qvec = self.embedder.embed_query(query)  # o embedder aplica prefixo, se houver
        con = duckdb.connect(self.db_path, read_only=True)
        where = ""
        params: list = [qvec]
        if domains:
            where = f" WHERE domain IN ({', '.join('?' for _ in domains)})"
            params += list(domains)
        dense = con.execute(
            f"""SELECT id, text, source,
                       array_cosine_similarity(embedding, ?::FLOAT[{EMBED_DIM}]) AS sim
                FROM knowledge_chunks{where}
                ORDER BY sim DESC""",
            params,
        ).fetchall()
        bm_rank = self._bm25(con, query)
        con.close()

        # Fusao: base = SIMILARIDADE semantica (preserva os gaps reais entre os chunks; num
        # corpus curado o embedding ja e forte). O BM25 entra so como um BONUS pequeno de
        # desempate, dando um empurrao a quem casa o termo exato — sem deixar palavra comum
        # ('FC', 'treino') derrubar o resultado semanticamente certo. Cresce em valor conforme
        # o corpus escala (onde termo exato/jargao pesa mais).
        BM25_BONUS = 0.005   # calibrado no conjunto-ouro: maior valor sem regressao (o denso
                             # manda no corpus atual; sobe conforme escalar)
        info = {rid: (text, source, sim) for rid, text, source, sim in dense}
        fused = []
        for rid, (_t, _s, sim) in info.items():
            score = sim + (BM25_BONUS / bm_rank[rid] if rid in bm_rank else 0.0)
            fused.append((rid, score))
        fused.sort(key=lambda x: x[1], reverse=True)

        out = []
        for rid, _score in fused:
            text, source, sim = info[rid]
            if sim < min_similarity:   # piso de relevancia (semantico) = anti-alucinacao
                continue
            out.append({"text": text, "source": source, "similarity": round(sim, 3)})
            if len(out) >= k:
                break
        return out

    def retrieve(self, query: str, k: int = 3, domains: "Optional[List[str]]" = None) -> list:
        """Interface BaseRetriever: usa o limiar proprio e marca origem 'curado'. `domains`
        (opcional) roteia por dominio — o contrato base segue valido quando nao passado."""
        hits = self.search(query, k=k, min_similarity=self.min_similarity, domains=domains)
        return [{"text": h["text"], "source": h["source"], "origin": "curado"} for h in hits]


def load_corpus(path: Path) -> List[Tuple[str, str, str]]:
    """Le um .md de fontes: chunks separados por '---', cada um com linha 'FONTE:' e
    (opcional) 'DOMINIO:' — o dominio roteia a busca (biomecanica|forca|calcado|treino|lesao).
    Sem DOMINIO, cai em 'geral' (retrocompativel)."""
    raw = Path(path).read_text(encoding="utf-8")
    chunks = []
    for block in raw.split("\n---\n"):
        block = block.strip()
        if not block:
            continue
        source, domain = "desconhecida", "geral"
        text_lines = []
        for line in block.splitlines():
            stripped = line.strip().upper()
            if stripped.startswith("FONTE:"):
                source = line.split(":", 1)[1].strip()
            elif stripped.startswith("DOMINIO:"):
                domain = line.split(":", 1)[1].strip().lower()
            else:
                text_lines.append(line)
        text = " ".join(text_lines).strip()
        if text:
            chunks.append((text, source, domain))
    return chunks


if __name__ == "__main__":
    # (Re)indexa o corpus com Contextual Retrieval. Rode apos editar fontes em rag/sources/.
    from analytics.llm import OllamaClient

    KNOWLEDGE_DB.unlink(missing_ok=True)  # reseta: schema pode ter mudado (search_text)
    kb = KnowledgeBase(embedder=OllamaEmbedder())
    # 7B (nao o 1.5b do rerank): indexacao e offline/manual, sem restricao de latencia — e o
    # 1.5b as vezes ignora a instrucao de formato (preambulo, aspas), poluindo o embedding.
    ctx_gen = ContextGenerator(OllamaClient(model="qwen2.5:7b-instruct", temperature=0.0))
    n = kb.index(load_corpus(PROJECT_ROOT / "rag" / "sources" / "corpus.md"), context_gen=ctx_gen)
    print(f"Base de conhecimento (re)indexada com contexto: {n} chunks.")
