"""api/main.py — Gateway REST do StriderEdge OS (FastAPI).

Endpoints FINOS (controllers): validam entrada e delegam às classes de serviço
(`ActivityService`, `Coach`) injetadas via Depends. REST + gzip nas respostas
grandes. Concorrência = async/threadpool do FastAPI; o paralelismo mora no kernel Rust.
"""

import json
import time
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from core.logging import Logger
from analytics.coach import Coach
from analytics.fitness import RunningFitness
from analytics.sql_agent import SqlAgent
from analytics.training_load import TrainingLoad
from api.auth import AuthError, AuthService
from api.form import FormService
from api.services import ActivityService
from api.deps import (get_activity_service, get_auth_service, get_coach, get_form_service,
                      get_running_fitness, get_sql_agent, get_training_load)


class AskRequest(BaseModel):
    question: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleRequest(BaseModel):
    credential: str

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


# ---------- Auth (contas) ----------

def _auth_call(fn, *args):
    """Traduz AuthError -> HTTPException (controllers finos, regra no serviço)."""
    try:
        return fn(*args)
    except AuthError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


@app.post("/api/v1/auth/register", status_code=201)
def auth_register(req: RegisterRequest, auth: AuthService = Depends(get_auth_service)):
    """Cadastro único por e-mail; senha vira scrypt+salt (nunca em claro)."""
    return _auth_call(auth.register, req.name, req.email, req.password)


@app.post("/api/v1/auth/login")
def auth_login(req: LoginRequest, auth: AuthService = Depends(get_auth_service)):
    return _auth_call(auth.login, req.email, req.password)


@app.post("/api/v1/auth/google")
def auth_google(req: GoogleRequest, auth: AuthService = Depends(get_auth_service)):
    """Login/cadastro com o ID token do Google (exige GOOGLE_CLIENT_ID no ambiente)."""
    return _auth_call(auth.login_google, req.credential)


@app.get("/api/v1/auth/me")
def auth_me(request: Request, auth: AuthService = Depends(get_auth_service)):
    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    return _auth_call(auth.me, token)


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


@app.get("/api/v1/activities/{activity_id}/sets")
def activity_sets(activity_id: str):
    """Séries de força + músculos trabalhados (vazio fora do modo Força — gracioso)."""
    _ensure_uuid(activity_id)
    from analytics.strength import StrengthSets
    return {"activity_id": activity_id, **StrengthSets().summary(activity_id)}


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


# ---------- Análise de Forma (stride-vision) ----------

@app.post("/api/v1/form", status_code=201)
async def form_upload(video: UploadFile = File(...), activity_id: str = Form(None),
                      svc: FormService = Depends(get_form_service)):
    """Recebe o vídeo, salva no filesystem e processa em background (motor Rust)."""
    if activity_id:
        _ensure_uuid(activity_id)
    data = await video.read()
    if len(data) > 300 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Vídeo grande demais (max 300MB)")
    return svc.create(data, video.filename or "video.mp4", activity_id)


@app.get("/api/v1/form")
def form_list(activity_id: str = None, svc: FormService = Depends(get_form_service)):
    if activity_id:
        _ensure_uuid(activity_id)
    return svc.list(activity_id)


@app.get("/api/v1/form/{analysis_id}")
def form_get(analysis_id: str, svc: FormService = Depends(get_form_service)):
    _ensure_uuid(analysis_id)
    row = svc.get(analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    return row


@app.get("/api/v1/form/{analysis_id}/video")
def form_video(analysis_id: str, svc: FormService = Depends(get_form_service)):
    """Serve o overlay.mp4 (esqueleto desenhado) direto do filesystem."""
    _ensure_uuid(analysis_id)
    path = svc.video_path(analysis_id)
    if not path:
        raise HTTPException(status_code=404, detail="Vídeo não disponível")
    return FileResponse(path, media_type="video/mp4")


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
