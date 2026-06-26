"""api/main.py — Gateway REST do StriderEdge OS (FastAPI).

Endpoints FINOS (controllers): validam entrada e delegam às classes de serviço
(`ActivityService`, `Coach`) injetadas via Depends. REST + gzip nas respostas
grandes. Concorrência = async/threadpool do FastAPI; o paralelismo mora no kernel Rust.
"""

import time
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from core.logging import Logger
from analytics.coach import Coach
from analytics.sql_agent import SqlAgent
from analytics.training_load import TrainingLoad
from api.services import ActivityService
from api.deps import get_activity_service, get_coach, get_sql_agent, get_training_load


class AskRequest(BaseModel):
    question: str

app = FastAPI(title="StriderEdge OS API", version="1.0.0")
app.add_middleware(GZipMiddleware, minimum_size=1000)  # compacta payloads grandes (telemetria)

_log = Logger("api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Loga cada requisição com trace_id + duração (observabilidade)."""
    trace_id = uuid4().hex[:8]
    start = time.perf_counter()
    response = await call_next(request)
    _log.info("request", trace_id=trace_id, method=request.method,
              path=request.url.path, status=response.status_code,
              ms=round((time.perf_counter() - start) * 1000, 1))
    return response


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


@app.get("/api/v1/training-load")
def training_load(tl: TrainingLoad = Depends(get_training_load)):
    """Linha do tempo de carga + ACWR (com portão de confiança) — nível atleta."""
    return tl.acwr_timeline()


@app.post("/api/v1/ask")
def ask(req: AskRequest, agent: SqlAgent = Depends(get_sql_agent)):
    """Coach agêntico: pergunta em linguagem natural → SQL → resposta."""
    result = agent.answer(req.question)
    return {"question": req.question, **result}
