"""rag/contextualize.py — geracao de contexto por chunk (Contextual Retrieval, Anthropic set/2024).

Cada chunk do corpus e uma frase atomica isolada; o contexto (1 frase) ancora o chunk
ao ESTUDO/TEMA de origem, ajudando BM25 e o denso quando a pergunta usa vocabulario
diferente do chunk. So roda no INDEX (offline, script de reindexacao); nao entra no
caminho de retrieve/search (que fica sem chamada extra de LLM, sem custo de latencia).
"""

import re

from core.framework.interfaces import BaseLLMClient

# Remove preambulos que o LLM as vezes cola na frente ("Contexto:", "A frase seria:") e aspas
# envolvendo a resposta inteira — defesa extra alem da instrucao no prompt.
_PREAMBLE_RE = re.compile(r'^\s*(?:contexto|context)\s*:\s*', re.IGNORECASE)
_QUOTE_RE = re.compile(r'^["\'“](.*)["\'”]$', re.DOTALL)

_SYSTEM = (
    "Voce escreve uma frase curta (ate 15 palavras) de CONTEXTO para um trecho de um corpus "
    "cientifico sobre corrida, nomeando o TEMA e a METRICA do estudo de origem. Responda "
    "DIRETO com a frase, sem preambulo ('a frase seria', 'contexto:'), sem aspas, sem "
    "repetir o trecho literal."
)


class ContextGenerator:
    """Gera o blurb de contexto de um chunk via LLM local. COMPOE um BaseLLMClient (mesmo
    padrao do Coach/LLMReranker) — troca de modelo sem mudar quem usa. Degrada gracioso:
    falha do LLM -> string vazia (o chamador cai de volta ao texto puro)."""

    def __init__(self, llm: BaseLLMClient):
        self.llm = llm

    def generate(self, chunk_text: str, source: str) -> str:
        user = f"FONTE: {source}\n\nTRECHO:\n{chunk_text}\n\nContexto:"
        try:
            out = self.llm.chat(_SYSTEM, user).strip()
        except Exception:
            return ""
        out = _PREAMBLE_RE.sub("", out).strip()
        m = _QUOTE_RE.match(out)
        return m.group(1).strip() if m else out
