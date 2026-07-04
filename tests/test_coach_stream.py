"""Testes do cache de veredito (VerdictStore) e do streaming (stream_verdict + SSE).

Tudo com LLM fake (sem Ollama) sobre o banco temporário do conftest.
"""

import pytest
from fastapi.testclient import TestClient

from analytics.coach import Coach, VerdictStore
from api.deps import get_coach
from api.main import app
from core.database import get_connection
from core.framework.interfaces import BaseLLMClient

FLORIPA_ID = "22222222-2222-2222-2222-222222222222"   # semeada no conftest

client = TestClient(app)


class CountingLLM(BaseLLMClient):
    """Fake que conta chamadas — prova idempotência (cache não re-chama o LLM)."""

    def __init__(self, reply: str = "VEREDITO_FAKE"):
        self.reply = reply
        self.calls = 0

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return self.reply


class DirtyThenCleanLLM(BaseLLMClient):
    """1ª resposta inventa número (guarda reprova); 2ª vem limpa."""

    def __init__(self):
        self.calls = 0

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return "Voce correu 987654 km hoje." if self.calls == 1 else "Ritmo constante, sem quebra."


@pytest.fixture(autouse=True)
def _clean_cache():
    get_connection().execute("DELETE FROM cache_coach_verdicts")
    yield


def test_store_roundtrip():
    store = VerdictStore()
    structured = {"verdict": "texto", "strengths": ["a"], "improvements": [],
                  "actions": ["b"], "citations": ["PMC1"]}
    store.put(FLORIPA_ID, structured, model="fake")
    hit = store.get(FLORIPA_ID)
    assert hit["verdict"] == "texto" and hit["actions"] == ["b"]
    assert "generated_at" in hit
    assert store.get("00000000-0000-0000-0000-000000000000") is None


def test_cached_verdict_e_idempotente():
    llm = CountingLLM()
    coach = Coach(llm=llm)
    first = coach.cached_verdict(FLORIPA_ID)
    second = coach.cached_verdict(FLORIPA_ID)
    assert llm.calls == 1                      # 2º POST não pagou outro LLM
    assert first["cached"] is False and second["cached"] is True
    assert second["verdict"] == "VEREDITO_FAKE"


def test_force_regenera():
    llm = CountingLLM()
    coach = Coach(llm=llm)
    coach.cached_verdict(FLORIPA_ID)
    forced = coach.cached_verdict(FLORIPA_ID, force=True)
    assert llm.calls == 2 and forced["cached"] is False


def test_stream_limpo_token_e_done():
    coach = Coach(llm=CountingLLM())
    events = list(coach.stream_verdict(FLORIPA_ID))
    kinds = [e for e, _ in events]
    assert kinds == ["token", "done"]          # fake = 1 chunk; guarda limpa
    assert events[-1][1]["verdict"] == "VEREDITO_FAKE"
    # done persiste no cache -> próximo stream devolve 'done' direto
    kinds2 = [e for e, _ in coach.stream_verdict(FLORIPA_ID)]
    assert kinds2 == ["done"]


def test_stream_corrige_quando_guarda_reprova():
    llm = DirtyThenCleanLLM()
    coach = Coach(llm=llm)
    events = list(coach.stream_verdict(FLORIPA_ID))
    kinds = [e for e, _ in events]
    assert kinds == ["token", "correcting", "replace", "done"]
    assert "987654" in events[0][1]            # streamou a versão suja
    assert events[2][1] == "Ritmo constante, sem quebra."   # replace = corrigida
    assert events[3][1]["verdict"] == "Ritmo constante, sem quebra."
    assert llm.calls == 2                      # enforce continuou da 1ª (first=), sem regerar


def test_api_post_coach_cacheia():
    app.dependency_overrides[get_coach] = lambda: Coach(llm=CountingLLM())
    try:
        r1 = client.post(f"/api/v1/activities/{FLORIPA_ID}/coach")
        r2 = client.post(f"/api/v1/activities/{FLORIPA_ID}/coach")
        assert r1.json()["cached"] is False and r2.json()["cached"] is True
        r3 = client.post(f"/api/v1/activities/{FLORIPA_ID}/coach?force=true")
        assert r3.json()["cached"] is False
    finally:
        app.dependency_overrides.clear()


def test_api_sse_stream():
    app.dependency_overrides[get_coach] = lambda: Coach(llm=CountingLLM())
    try:
        r = client.get(f"/api/v1/activities/{FLORIPA_ID}/coach/stream")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert "event: token" in r.text and "event: done" in r.text
        assert "VEREDITO_FAKE" in r.text
    finally:
        app.dependency_overrides.clear()
