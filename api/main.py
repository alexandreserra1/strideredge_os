"""api/main.py — Gateway REST do StriderEdge OS (FastAPI).

Endpoints FINOS (controllers): validam entrada e delegam às classes de serviço
(`ActivityService`, `Coach`) injetadas via Depends. REST + gzip nas respostas
grandes. Concorrência = async/threadpool do FastAPI; o paralelismo mora no kernel Rust.
"""

from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from analytics.coach import Coach
from analytics.sql_agent import SqlAgent
from api.services import ActivityService
from api.deps import get_activity_service, get_coach, get_sql_agent


class AskRequest(BaseModel):
    question: str

app = FastAPI(title="StriderEdge OS API", version="1.0.0")
app.add_middleware(GZipMiddleware, minimum_size=1000)  # compacta payloads grandes (telemetria)


def _ensure_uuid(activity_id: str) -> None:
    """String que não é UUID = 404 (não 500)."""
    try:
        UUID(activity_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")


@app.get("/api/v1/activities")
def list_activities(svc: ActivityService = Depends(get_activity_service)):
    return svc.list()


@app.get("/api/v1/activities/{activity_id}")
def activity_detail(activity_id: str, svc: ActivityService = Depends(get_activity_service)):
    _ensure_uuid(activity_id)
    detail = svc.detail(activity_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")
    return detail


@app.get("/api/v1/activities/{activity_id}/track")
def activity_track(activity_id: str, svc: ActivityService = Depends(get_activity_service)):
    _ensure_uuid(activity_id)
    return svc.track(activity_id)


@app.get("/api/v1/activities/{activity_id}/telemetry")
def activity_telemetry(activity_id: str, svc: ActivityService = Depends(get_activity_service)):
    _ensure_uuid(activity_id)
    return svc.telemetry(activity_id)


@app.get("/api/v1/activities/{activity_id}/cadence-spectrum")
def activity_spectrum(activity_id: str, svc: ActivityService = Depends(get_activity_service)):
    _ensure_uuid(activity_id)
    return svc.spectrum(activity_id)


@app.post("/api/v1/activities/{activity_id}/coach")
def coach_verdict(activity_id: str, coach: Coach = Depends(get_coach)):
    _ensure_uuid(activity_id)
    return {"activity_id": activity_id, "verdict": coach.verdict(activity_id)}


@app.post("/api/v1/ask")
def ask(req: AskRequest, agent: SqlAgent = Depends(get_sql_agent)):
    """Coach agêntico: pergunta em linguagem natural → SQL → resposta."""
    result = agent.answer(req.question)
    return {"question": req.question, **result}
