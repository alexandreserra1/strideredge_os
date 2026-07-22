"""Testa a recomendação de tênis (EPIC D) com fakes — sem Ollama nem RAG real.

Cobre as regras determinísticas honestas: antepé→drop baixo, calcanhar→drop alto, peso>85→cautela
minimalista, caveats de honestidade obrigatórios, e fontes vindas do retriever mockado.
"""

import os
import pytest

from analytics.shoe import recommend, ShoeRecommender


class _FakeKB:
    """Retriever falso do domínio calcado: devolve uma fonte com PMC estável."""
    def __init__(self):
        self.last_domains = None

    def retrieve(self, query, k=3, domains=None):
        self.last_domains = domains
        return [{"text": "casar tenis com a pisada guia o drop", "origin": "curado",
                 "source": "Acute Effects of Heel-to-Toe Drop (PMC8833076)"}]


class _FakeLLM:
    def chat(self, system_prompt, user_prompt):
        return "Escolhemos essa faixa pela sua pisada. Lembre: tenis e ajuste de carga, nao previne lesao."


def test_antepe_drop_baixo():
    out = recommend("antepe")
    assert out["drop_mm"].startswith("4-6")
    assert "uniforme" in out["cushioning"]


def test_calcanhar_drop_alto():
    out = recommend("calcanhar")
    assert out["drop_mm"].startswith("8-10")
    assert "retropé" in out["cushioning"]


def test_peso_alto_cautela_minimalista():
    out = recommend("calcanhar", weight_kg=92.0)
    assert "minimalista" in out["cushioning"].lower()
    assert any("85" in t for t in out["tips"])


def test_caveats_honestidade_obrigatorios():
    """App de lesão: NUNCA prometer prevenção; mito da pronação, rodar ≥2 pares e a inferência
    da pisada têm que aparecer explicitamente."""
    cav = recommend("medio")["caveat"].lower()
    assert "não previne" in cav or "nao previne" in cav or "não cura" in cav or "nao cura" in cav
    assert "pronação" in cav or "pronacao" in cav
    assert "pares" in cav                     # rodar ≥2 pares
    assert "inferência" in cav or "inferencia" in cav   # pisada é inferência


def test_historico_joelho_migra_drop_menor():
    out = recommend("calcanhar", history={"regions": ["joelho_frente"]})
    assert "GRADUALMENTE" in out["drop_mm"]
    assert any("joelho" in t.lower() for t in out["tips"])


def test_historico_aquiles_drop_maior():
    out = recommend("antepe", history={"regions": ["tornozelo"]})
    assert out["drop_mm"].startswith("6-8")


def test_sources_deterministicas_sao_ids_estaveis():
    out = recommend("calcanhar", weight_kg=90.0)
    assert "PMC8833076" in out["sources"]                # pisada↔drop
    assert any(s.startswith("DOI:10.3389") for s in out["sources"])  # peso/minimalista
    assert any(s.startswith("DOI:") or s.startswith("PMC") for s in out["sources"])


def test_recommender_cita_fontes_do_retriever_mockado():
    kb = _FakeKB()
    rec = ShoeRecommender(knowledge=kb)
    out = rec.recommend("antepe", weight_kg=70.0)
    assert kb.last_domains == ["calcado"]                # roteou por domínio
    assert "PMC8833076" in out["sources"]                # fonte recuperada citada


def test_recommender_degrada_sem_rag():
    """Sem retriever, mantém as regras determinísticas + caveats (degrada gracioso)."""
    out = ShoeRecommender().recommend("calcanhar")
    assert out["drop_mm"].startswith("8-10")
    assert out["caveat"] and out["sources"]


def test_cover_humana_com_llm_aterrado():
    rec = ShoeRecommender(llm=_FakeLLM(), knowledge=_FakeKB())
    out = rec.recommend("antepe", write_cover=True)
    assert "cover" in out and "carga" in out["cover"].lower()


@pytest.mark.skipif(not os.environ.get("OLLAMA_E2E"), reason="requer Ollama up (OLLAMA_E2E=1)")
def test_recomendacao_citada_real_e2e():
    """E2E real: KnowledgeBase real roteado em calcado; só roda com Ollama up."""
    from analytics.llm import OllamaClient
    from rag.knowledge_base import KnowledgeBase, OllamaEmbedder
    try:
        kb = KnowledgeBase(embedder=OllamaEmbedder())
        rec = ShoeRecommender(llm=OllamaClient(), knowledge=kb)
        out = rec.recommend("antepe", weight_kg=90.0, write_cover=True)
    except Exception as e:
        pytest.skip(f"Ollama/RAG indisponível: {e}")
    assert out["sources"]                                 # citou
    assert "previne" in out["cover"].lower() or "carga" in out["cover"].lower()
    print("\nE2E shoe:", out["cushioning"], out["drop_mm"], "->", out["sources"])


def test_pisada_acentuada_do_motor_normaliza():
    # o stride_vision emite "antepé"/"médio" COM acento — não pode cair no default de calcanhar
    from analytics.shoe import recommend
    assert recommend("antepé", weight_kg=70.0)["drop_mm"] == "4-6"
    assert recommend("médio", weight_kg=70.0)["drop_mm"] == "4-6"
    assert recommend("calcanhar", weight_kg=70.0)["drop_mm"] == "8-10"


def test_endpoint_shoe_sanitiza_metrica_impossivel():
    """Regressão: oscilação vertical impossível (24,7% = artefato de medição) NÃO pode virar
    conselho de tênis. O endpoint /shoe sanitiza igual ao coach/plano (trava o dado no consumidor)."""
    import json
    import uuid
    from fastapi.testclient import TestClient
    from api.main import app
    from api.deps import get_shoe_recommender
    from analytics.shoe import ShoeRecommender
    from core.database import get_connection

    client = TestClient(app)
    aid = str(uuid.uuid4())
    metrics = {"foot_strike": "antepé", "vertical_oscillation_pct": 24.7, "reliable": True}
    con = get_connection()
    con.execute("INSERT INTO form_analyses (analysis_id, status, modality, metrics) "
                "VALUES (?, 'done', 'run', ?)", [aid, json.dumps(metrics)])
    app.dependency_overrides[get_shoe_recommender] = lambda: ShoeRecommender()  # sem LLM/RAG (hermético)
    try:
        r = client.post(f"/api/v1/form/{aid}/shoe")
        assert r.status_code == 200
        body = r.json()
        assert not any("oscila" in t.lower() for t in body["tips"])   # artefato foi sanitizado
        assert body["drop_mm"] == "4-6"                                # pisada antepé segue valendo
    finally:
        app.dependency_overrides.clear()
        con.execute("DELETE FROM form_analyses WHERE analysis_id=?", [aid])
