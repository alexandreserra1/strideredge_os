"""api/main.py — Gateway REST do StriderEdge OS (FastAPI).

Endpoints FINOS (controllers): validam entrada e delegam às classes de serviço
(`ActivityService`, `Coach`) injetadas via Depends. REST + gzip nas respostas
grandes. Concorrência = async/threadpool do FastAPI; o paralelismo mora no kernel Rust.
"""

import json
import time
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.logging import Logger
from analytics.coach import Coach
from analytics.fitness import RunningFitness
from analytics.sql_agent import SqlAgent
from analytics.training_load import TrainingLoad
from api.services import ActivityService
from api.deps import (get_activity_service, get_coach, get_running_fitness,
                      get_sql_agent, get_training_load)


class AskRequest(BaseModel):
    question: str

app = FastAPI(title="StriderEdge OS API", version="1.0.0")
app.add_middleware(GZipMiddleware, minimum_size=1000)  # compacta payloads grandes (telemetria)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
def coach_verdict(activity_id: str, force: bool = False, coach: Coach = Depends(get_coach)):
    """Veredito estruturado COM cache (idempotente: repetir devolve o persistido).
    ?force=true regenera. Resposta inclui cached: bool."""
    _ensure_uuid(activity_id)
    return {"activity_id": activity_id, **coach.cached_verdict(activity_id, force=force)}


@app.get("/api/v1/activities/{activity_id}/coach/stream")
def coach_verdict_stream(activity_id: str, force: bool = False, coach: Coach = Depends(get_coach)):
    """Veredito em STREAMING (SSE): 'token' conforme o LLM gera; 'correcting'/'replace' se a
    guarda de aterramento reprovar; 'done' com o estruturado (persistido). Cache -> 'done' direto."""
    _ensure_uuid(activity_id)

    def sse():
        for event, payload in coach.stream_verdict(activity_id, force=force):
            data = {"text": payload} if isinstance(payload, str) else payload
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/v1/training-load")
def training_load(tl: TrainingLoad = Depends(get_training_load)):
    """Linha do tempo de carga + ACWR (com portão de confiança) — nível atleta."""
    return tl.acwr_timeline()


@app.get("/api/v1/fitness")
def fitness(rf: RunningFitness = Depends(get_running_fitness)):
    """Previsão de prova (Riegel) + tendência de fitness — nível atleta."""
    return rf.summary()


@app.post("/api/v1/ask")
def ask(req: AskRequest, agent: SqlAgent = Depends(get_sql_agent)):
    """Coach agêntico: pergunta em linguagem natural → SQL → resposta."""
    result = agent.answer(req.question)
    return {"question": req.question, **result}
