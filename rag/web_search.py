"""rag/web_search.py — fallback de busca na web (RAG hibrido).

Usado SO quando a base curada nao tem evidencia relevante. Restrito a dominios
confiaveis (PubMed/PMC, OMS, NIH/CDC) — fonte menos controlada que a curada, por
isso marcada como 'web' e usada apenas como ultimo recurso.

Implementa BaseRetriever: mesma interface da KnowledgeBase (polimorfismo).
"""

from typing import List
from urllib.parse import urlparse

from core.framework.interfaces import BaseRetriever

# So fontes de autoridade reconhecida (app de risco de lesao).
REPUTABLE_DOMAINS = ["ncbi.nlm.nih.gov", "who.int", "nih.gov", "cdc.gov"]


class WebSearchRetriever(BaseRetriever):
    """Busca referencias na web (DuckDuckGo) restrita a dominios confiaveis."""

    def __init__(self, domains: List[str] = None):
        self.domains = domains or REPUTABLE_DOMAINS

    def _search_raw(self, query: str, max_results: int) -> list:
        """Chamada de rede crua (ddgs), restrita aos dominios confiaveis.

        Isolada do filtro para ser testavel: nos testes, sobrescrevemos este metodo
        com resultados fixos e nao tocamos a internet.
        """
        site_filter = " OR ".join(f"site:{d}" for d in self.domains)
        try:
            from ddgs import DDGS
            return DDGS().text(f"{query} ({site_filter})", max_results=max_results)
        except Exception:
            return []  # sem internet / busca falhou -> degrada gracioso

    def retrieve(self, query: str, k: int = 3) -> list:
        results = self._search_raw(query, max_results=k * 2)
        out = []
        for r in results:
            href = r.get("href", "")
            body = (r.get("body") or "").strip()
            has_article_path = bool(urlparse(href).path.strip("/"))  # evita homepage do dominio
            # so aceita dominio confiavel E pagina de artigo (nao a raiz do site)
            if body and has_article_path and any(d in href for d in self.domains):
                out.append({"text": body, "source": href, "origin": "web"})
            if len(out) >= k:
                break
        return out
