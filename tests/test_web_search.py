"""Testes do filtro do fallback de web — sem internet.

Sobrescrevemos `_search_raw` (a chamada de rede) com resultados fixos e testamos
SÓ a lógica de filtro: aceitar apenas domínio confiável + página de artigo (não a
homepage), e marcar origem 'web'.
"""

from rag.web_search import WebSearchRetriever


class FakeWeb(WebSearchRetriever):
    """Versão testável: resultados fixos no lugar da busca real."""

    def __init__(self, fixed_results):
        super().__init__()
        self._fixed = fixed_results

    def _search_raw(self, query, max_results):
        return self._fixed


def test_filter_keeps_only_reputable_article_pages():
    web = FakeWeb([
        {"href": "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/", "body": "estudo real sobre corrida"},
        {"href": "https://pubmed.ncbi.nlm.nih.gov/", "body": "homepage do pubmed"},       # sem caminho
        {"href": "https://blogqualquer.com/dicas", "body": "blog nao confiavel"},          # dominio ruim
    ])
    hits = web.retrieve("qualquer coisa", k=3)
    assert len(hits) == 1
    assert hits[0]["source"] == "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/"
    assert hits[0]["origin"] == "web"


def test_empty_results_degrade_gracefully():
    web = FakeWeb([])
    assert web.retrieve("nada", k=3) == []


def test_drops_results_without_body():
    web = FakeWeb([
        {"href": "https://pmc.ncbi.nlm.nih.gov/articles/PMC999/", "body": ""},  # sem texto
    ])
    assert web.retrieve("x", k=3) == []
