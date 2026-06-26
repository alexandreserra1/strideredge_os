"""Testes de contrato da API REST (TDD) — FastAPI TestClient, determinísticos.

Endpoints de leitura batem no DuckDB já semeado. O endpoint do coach (lento/LLM) é
testado com um FakeLLM injetado via dependency_override — rápido e sem Ollama.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.deps import get_coach, get_sql_agent
from analytics.coach import Coach
from analytics.sql_agent import SqlAgent
from core.framework.interfaces import BaseLLMClient

client = TestClient(app)


class FakeLLM(BaseLLMClient):
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        return "VEREDITO_FAKE"


class FakeSqlLLM(BaseLLMClient):
    """Devolve SQL na geração (SYSTEM_SQL) e prosa no resumo (SYSTEM_ANSWER)."""

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        if "traduz" in system_prompt.lower():
            return "SELECT COUNT(*) AS n FROM dim_activities"
        return "RESPOSTA_FAKE"


def _activity_id(name: str = "Corrida Floripa") -> str:
    acts = client.get("/api/v1/activities").json()
    return next(a["activity_id"] for a in acts if a["activity_name"] == name)


def test_list_activities():
    r = client.get("/api/v1/activities")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and body
    assert {"activity_id", "activity_name", "primary_type"} <= set(body[0])


def test_activity_detail_ok():
    aid = _activity_id()
    r = client.get(f"/api/v1/activities/{aid}")
    assert r.status_code == 200
    body = r.json()
    assert body["activity_id"] == aid
    assert "breaking_point" in body and "hr_zones" in body and "efficiency" in body


def test_activity_detail_bad_uuid_returns_404():
    assert client.get("/api/v1/activities/not-a-uuid").status_code == 404


def test_activity_detail_missing_returns_404():
    r = client.get("/api/v1/activities/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_track_has_smoothed_coords():
    r = client.get(f"/api/v1/activities/{_activity_id()}/track")
    assert r.status_code == 200
    assert "smooth" in r.json() and "latitude" in r.json()["smooth"]


def test_telemetry_series():
    r = client.get(f"/api/v1/activities/{_activity_id()}/telemetry")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and body
    assert {"timestamp", "heart_rate", "cadence"} <= set(body[0])


def test_cadence_spectrum():
    r = client.get(f"/api/v1/activities/{_activity_id()}/cadence-spectrum")
    assert r.status_code == 200
    assert "dominant_frequency_hz" in r.json() and "spectrum" in r.json()


def test_coach_endpoint_with_fake_llm():
    app.dependency_overrides[get_coach] = lambda: Coach(llm=FakeLLM())
    try:
        r = client.post(f"/api/v1/activities/{_activity_id()}/coach")
        assert r.status_code == 200
        assert r.json()["verdict"] == "VEREDITO_FAKE"
    finally:
        app.dependency_overrides.clear()


def test_ask_endpoint_with_fake_llm():
    app.dependency_overrides[get_sql_agent] = lambda: SqlAgent(llm=FakeSqlLLM())
    try:
        r = client.post("/api/v1/ask", json={"question": "quantos treinos eu tenho?"})
        assert r.status_code == 200
        body = r.json()
        assert body["answer"] == "RESPOSTA_FAKE"
        assert body["sql"].lower().startswith("select")
    finally:
        app.dependency_overrides.clear()


def test_ask_validation_requires_question():
    assert client.post("/api/v1/ask", json={}).status_code == 422


def test_training_load_endpoint():
    r = client.get("/api/v1/training-load")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and body
    assert {"day", "acwr", "status", "ramp_pct"} <= set(body[0])
