"""api/main.py — Gateway REST do StriderEdge OS (FastAPI).

App focado em ANÁLISE DE FORMA POR VÍDEO (prevenção de lesão): auth, upload/consulta de
análise de forma e o plano corretivo citado. Controllers FINOS: validam entrada e delegam
às classes de serviço injetadas via Depends. Processamento pesado (motor de visão) roda em
background pela fila de jobs — o request só enfileira e responde na hora.
"""

import time
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.logging import Logger
from analytics.form_coach import FormCoach
from analytics.injury_dataset import injury_history
from analytics.injury_quality import sanitize_metrics
from analytics.training_plan import plan_from_metrics
from analytics.injury_taxonomy import taxonomy_payload
from api.auth import AuthError, AuthService
from api.form import FormService
from api.injuries import InjuryError, InjuryService
from api.profile import ProfileService
from api.deps import (get_auth_service, get_diagnosis_classifier, get_form_coach, get_form_service,
                      get_injury_service, get_job_queue, get_plan_service, get_profile_service,
                      get_shoe_recommender)


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleRequest(BaseModel):
    credential: str


class ProfileRequest(BaseModel):
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    years_running: Optional[float] = None
    goal: Optional[str] = None
    goal_timeframe_weeks: Optional[int] = None
    weekly_volume_km: Optional[float] = None
    days_per_week: Optional[int] = None
    current_shoe: Optional[str] = None
    footstrike_pref: Optional[str] = None


class InjuryRequest(BaseModel):
    region: Optional[str] = None
    diagnosis: Optional[str] = None
    side: Optional[str] = None
    onset_date: Optional[str] = None
    q_participation: Optional[int] = None
    q_volume: Optional[int] = None
    q_performance: Optional[int] = None
    q_pain: Optional[int] = None
    symptom_text: Optional[str] = None
    notes: Optional[str] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Boot da API: carrega o .env (credenciais Google), sobe o pool de workers da fila de
    jobs e recupera análises órfãs (crash: linhas 'processing' de quando o servidor caiu no
    meio do job de vídeo)."""
    from api.form import recover_orphaned_analyses
    from core.database import get_connection, run_migrations
    from core.env import load_dotenv
    load_dotenv()
    run_migrations(get_connection())   # idempotente (IF NOT EXISTS) — schema sempre em dia no boot
    get_job_queue().start()
    recover_orphaned_analyses()
    yield


app = FastAPI(title="StriderEdge OS API", version="2.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)  # compacta respostas grandes (métricas)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_log = Logger("api")

# Declara a config efetiva no boot (ambiente) — observabilidade.
from core.config import summary as _config_summary  # noqa: E402
_log.info("boot", **_config_summary())


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


def _ensure_uuid(value: str) -> None:
    """String que não é UUID = 404 (não 500)."""
    try:
        UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail="Não encontrado")


# ---------- Auth (contas) ----------

def _auth_call(fn, *args):
    """Traduz AuthError -> HTTPException (controllers finos, regra no serviço)."""
    try:
        return fn(*args)
    except AuthError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


@app.post("/api/v1/auth/register", status_code=201)
def auth_register(req: RegisterRequest, auth: AuthService = Depends(get_auth_service)):
    """Cadastro único por e-mail; senha vira PBKDF2+salt (nunca em claro)."""
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


# ---------- Análise de Forma por vídeo (stride-vision) ----------

@app.post("/api/v1/form", status_code=201)
async def form_upload(request: Request, video: UploadFile = File(...), modality: str = Form("run"),
                      view: str = Form("lateral"), svc: FormService = Depends(get_form_service),
                      auth: AuthService = Depends(get_auth_service)):
    """Recebe o vídeo, salva no filesystem e ENFILEIRA o processamento (motor Rust em
    background). Responde 'processing' na hora — o usuário pode fechar a página e voltar.
    `view` = 'lateral' | 'frontal' (conjunto de métricas por vista). Liga ao usuário se logado
    (pra correlação com lesão); convidado fica anônimo."""
    data = await video.read()
    if len(data) > 300 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Vídeo grande demais (max 300MB)")
    user_id = None
    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    try:
        user_id = auth.me(token)["user_id"]
    except AuthError:
        pass   # convidado -> análise anônima (degrada gracioso)
    return svc.create(data, video.filename or "video.mp4", None, modality or "run",
                      view or "lateral", user_id)


@app.get("/api/v1/form")
def form_list(svc: FormService = Depends(get_form_service)):
    return svc.list()


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


@app.post("/api/v1/form/{analysis_id}/coach")
def form_coach(analysis_id: str, request: Request,
               form: FormService = Depends(get_form_service),
               coach: FormCoach = Depends(get_form_coach),
               profiles: ProfileService = Depends(get_profile_service),
               auth: AuthService = Depends(get_auth_service)):
    """Algoritmo Corretivo: das métricas do vídeo -> plano de correção com exercícios citados.
    Usa o perfil do usuário logado (se houver) pra personalizar os alvos."""
    _ensure_uuid(analysis_id)
    row = form.get(analysis_id)
    if row is None or row.get("metrics") is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada ou ainda sem métricas")
    profile, history = None, None
    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    try:
        uid = auth.me(token)["user_id"]
        profile = profiles.get(uid)
        history = injury_history(uid)   # lesão prévia sensibiliza o risco (preditor #1)
    except AuthError:
        pass   # sem login -> alvos populacionais + sem histórico (degrada gracioso)
    return {"analysis_id": analysis_id,
            **coach.plan(row["metrics"], profile=profile, history=history)}


@app.post("/api/v1/form/{analysis_id}/shoe")
def form_shoe(analysis_id: str, request: Request, cover: bool = False,
              form: FormService = Depends(get_form_service),
              recommender=Depends(get_shoe_recommender),
              profiles: ProfileService = Depends(get_profile_service),
              auth: AuthService = Depends(get_auth_service)):
    """Recomendação de tênis (EPIC D): pisada + oscilação (métricas do vídeo) + peso (perfil) +
    histórico de lesão (logado) → faixa de amortecimento/drop honesta e citada. `cover=1` pede a
    capa humana pelo LLM. Espelha o padrão do /coach; degrada gracioso sem login."""
    _ensure_uuid(analysis_id)
    row = form.get(analysis_id)
    if row is None or row.get("metrics") is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada ou ainda sem métricas")
    # Sanitiza como o coach/plano: métrica impossível (ex.: oscilação vertical 24,7% = artefato)
    # NÃO pode virar conselho de tênis — o shoe é consumidor e trava o dado igual aos irmãos.
    metrics, _ = sanitize_metrics(row["metrics"])
    weight_kg, history = None, None
    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    try:
        uid = auth.me(token)["user_id"]
        weight_kg = (profiles.get(uid) or {}).get("weight_kg")
        history = injury_history(uid)   # lesão prévia por região ajusta o drop
    except AuthError:
        pass   # sem login -> só pisada/oscilação (degrada gracioso)
    rec = recommender.recommend(
        foot_strike=metrics.get("foot_strike"),
        vertical_oscillation_pct=metrics.get("vertical_oscillation_pct"),
        weight_kg=weight_kg, history=history, write_cover=cover)
    return {"analysis_id": analysis_id, **rec}


@app.post("/api/v1/form/{analysis_id}/plan")
def generate_plan(analysis_id: str, request: Request, weeks: int = 6,
                  form: FormService = Depends(get_form_service),
                  profiles: ProfileService = Depends(get_profile_service),
                  plans=Depends(get_plan_service),
                  auth: AuthService = Depends(get_auth_service)):
    """Plano corretivo de N semanas a partir da análise: desvios+risco+histórico → programa
    faseado citado. Usa `goal_timeframe_weeks` do perfil se `weeks` não vier. Persiste p/ logado."""
    _ensure_uuid(analysis_id)
    row = form.get(analysis_id)
    if row is None or row.get("metrics") is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada ou ainda sem métricas")
    profile, history, uid = None, None, None
    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    try:
        uid = auth.me(token)["user_id"]
        profile = profiles.get(uid)
        history = injury_history(uid)
    except AuthError:
        pass
    weeks = (profile or {}).get("goal_timeframe_weeks") or weeks   # prazo do atleta, se houver
    plan = plan_from_metrics(row["metrics"], weeks=weeks, profile=profile, history=history)
    if uid and not plan.get("unreliable"):
        plans.create(uid, analysis_id, plan)   # persiste o histórico de planos do atleta
    return {"analysis_id": analysis_id, "plan": plan}


@app.get("/api/v1/plans")
def list_plans(request: Request, plans=Depends(get_plan_service),
               auth: AuthService = Depends(get_auth_service)):
    """Planos corretivos gerados pelo atleta logado (mais recentes primeiro = progressão)."""
    return plans.list(_user_id(request, auth))


# ---------- Perfil do atleta (personaliza os alvos biomecânicos) ----------

def _user_id(request: Request, auth: AuthService) -> str:
    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    return _auth_call(auth.me, token)["user_id"]


@app.get("/api/v1/profile")
def get_profile(request: Request, auth: AuthService = Depends(get_auth_service),
                profiles: ProfileService = Depends(get_profile_service)):
    """Perfil do atleta logado (morfologia/hábitos). {} se ainda não preenchido."""
    return profiles.get(_user_id(request, auth)) or {}


@app.put("/api/v1/profile")
def put_profile(req: ProfileRequest, request: Request,
                auth: AuthService = Depends(get_auth_service),
                profiles: ProfileService = Depends(get_profile_service)):
    return profiles.upsert(_user_id(request, auth), req.model_dump())


# ---------- Lesões do atleta (log OSTRC — base do modelo de risco treinado) ----------

@app.get("/api/v1/injuries/taxonomy")
def injury_taxonomy():
    """Vocabulário controlado (região→diagnóstico→lado) pro picker do frontend. Público (só vocab)."""
    return taxonomy_payload()


@app.get("/api/v1/injuries")
def list_injuries(request: Request, auth: AuthService = Depends(get_auth_service),
                  injuries: InjuryService = Depends(get_injury_service)):
    """Lesões reportadas pelo atleta logado (com severidade OSTRC computada)."""
    return injuries.list(_user_id(request, auth))


@app.post("/api/v1/injuries", status_code=201)
def log_injury(req: InjuryRequest, request: Request,
               auth: AuthService = Depends(get_auth_service),
               injuries: InjuryService = Depends(get_injury_service)):
    """Registra uma lesão (vocabulário controlado da taxonomia + 4 perguntas OSTRC)."""
    try:
        return injuries.log(_user_id(request, auth), req.model_dump())
    except InjuryError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/v1/injuries/{injury_id}/classify")
def classify_injury(injury_id: str, request: Request,
                    auth: AuthService = Depends(get_auth_service),
                    injuries: InjuryService = Depends(get_injury_service),
                    classifier=Depends(get_diagnosis_classifier)):
    """Coach-time: mapeia o texto livre → diagnóstico da taxonomia (LLM, conjunto fechado +
    abstenção). Persiste só com confiança alta; do contrário mantém sem diagnóstico."""
    _user_id(request, auth)   # exige sessão
    report = injuries.classify(injury_id, classifier)
    if report is None:
        raise HTTPException(status_code=404, detail="lesão não encontrada")
    return report
