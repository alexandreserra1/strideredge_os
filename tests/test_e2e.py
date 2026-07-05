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


@pytest.mark.skipif(not _ollama_up(), reason="Ollama não está rodando")
def test_coach_stream_sse_live():
    """E2E do STREAMING: tokens chegam incrementalmente (muitos eventos, não 1 chunk)
    e 'done' fecha com o veredito estruturado. force=true ignora o cache de propósito."""
    events, done_payload = [], None
    with httpx.stream("GET", f"{API}/activities/{_floripa_id()}/coach/stream?force=true",
                      timeout=200) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        current = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                current = line[7:].strip()
                events.append(current)
            elif line.startswith("data: ") and current == "done":
                import json
                done_payload = json.loads(line[6:])
    assert events.count("token") > 10          # streaming real, não resposta única
    assert events[-1] == "done" and done_payload is not None
    assert done_payload["cached"] is False and len(done_payload["verdict"]) > 80


@pytest.mark.skipif(not _ollama_up(), reason="Ollama não está rodando")
def test_coach_cache_idempotente_live():
    """E2E da IDEMPOTÊNCIA: o 2º POST devolve o veredito persistido na hora
    (cached=true, <2s) em vez de pagar outros ~30s de LLM."""
    import time
    aid = _floripa_id()
    first = httpx.post(f"{API}/activities/{aid}/coach", timeout=200)
    assert first.status_code == 200
    t0 = time.perf_counter()
    second = httpx.post(f"{API}/activities/{aid}/coach", timeout=200)
    elapsed = time.perf_counter() - t0
    assert second.json()["cached"] is True and elapsed < 2.0
    assert second.json()["verdict"] == first.json()["verdict"]
