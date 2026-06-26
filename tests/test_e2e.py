"""Testes E2E (integração) — cliente HTTP PURO contra a API rodando.

Diferente de test_api.py (que sobe a app no processo e abre o DuckDB), aqui só
fazemos chamadas HTTP — então roda COM o servidor up, sem conflito de lock.

Pula sozinho se a API não responder em localhost:8000. Para rodar:
    uvicorn api.main:app      (em outro terminal)
    pytest tests/test_e2e.py
"""

import httpx
import pytest

API = "http://localhost:8000/api/v1"


def _api_up() -> bool:
    try:
        httpx.get(f"{API}/activities", timeout=2.0)
        return True
    except Exception:
        return False


def _ollama_up() -> bool:
    try:
        httpx.get("http://localhost:11434/api/version", timeout=2.0)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _api_up(), reason="API não está rodando em localhost:8000")


def _floripa_id() -> str:
    acts = httpx.get(f"{API}/activities", timeout=10).json()
    return next(a["activity_id"] for a in acts if a["activity_name"] == "Corrida Floripa")


def test_list_activities_live():
    r = httpx.get(f"{API}/activities", timeout=10)
    assert r.status_code == 200 and r.json()


def test_detail_live():
    r = httpx.get(f"{API}/activities/{_floripa_id()}", timeout=10)
    assert r.status_code == 200
    assert {"breaking_point", "hr_zones", "efficiency"} <= set(r.json())


def test_track_live():
    r = httpx.get(f"{API}/activities/{_floripa_id()}/track", timeout=15)
    assert r.status_code == 200 and "smooth" in r.json()


def test_bad_uuid_404_live():
    assert httpx.get(f"{API}/activities/not-a-uuid", timeout=10).status_code == 404


@pytest.mark.skipif(not _ollama_up(), reason="Ollama não está rodando")
def test_coach_live_pipeline():
    """E2E completo: API -> Coach -> Ollama -> RAG. Prova que a cadeia responde
    com um veredito substantivo. (A fidelidade/citação é medida no test_coach_eval.)"""
    r = httpx.post(f"{API}/activities/{_floripa_id()}/coach", timeout=200)
    assert r.status_code == 200
    verdict = r.json()["verdict"]
    assert isinstance(verdict, str) and len(verdict) > 80


@pytest.mark.skipif(not _ollama_up(), reason="Ollama não está rodando")
def test_ask_live_pipeline():
    """E2E do agêntico: pergunta -> LLM gera SQL -> executa -> resposta."""
    r = httpx.post(f"{API}/ask", json={"question": "quantos treinos de cada tipo eu tenho?"}, timeout=200)
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] and body["sql"].lower().startswith(("select", "with"))
