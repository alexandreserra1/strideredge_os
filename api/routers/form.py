"""api/routers/form.py — análise de forma por vídeo + coach/tênis/plano corretivo.

Controllers FINOS: validam entrada, extraem o usuário (opcional — degrada gracioso sem login) e
delegam aos serviços injetados. Processamento pesado (motor de visão) roda em background pela fila
de jobs; o upload só enfileira e responde 'processing' na hora."""

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from analytics.form_coach import FormCoach
from analytics.injury_dataset import injury_history
from analytics.injury_quality import sanitize_metrics
from analytics.training_plan import plan_from_metrics
from api.auth import AuthError, AuthService
from api.form import BackendConfigurationError, FormService, QueueFullError, VIDEOS_DIR
from api.profile import ProfileService
from api.deps import (get_auth_service, get_form_coach, get_form_progress_service, get_form_service, get_plan_service,
                      get_profile_service, get_shoe_recommender)
from api.routers.common import (analysis_token, bearer, ensure_uuid, limit_request,
                                optional_user_id, user_id)

router = APIRouter(tags=["form"])

_MAX_VIDEO_BYTES = 300 * 1024 * 1024
_MAX_MULTIPART_OVERHEAD = 2 * 1024 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _stage_upload(upload: UploadFile, remaining: int) -> tuple:
    """Copia por chunks para staging controlado e falha antes de exceder o teto combinado."""
    staging = VIDEOS_DIR / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(prefix="upload-", suffix=".part", dir=staging)
    path, size = Path(raw_path), 0
    try:
        with os.fdopen(fd, "wb") as dst:
            while chunk := await upload.read(_UPLOAD_CHUNK_BYTES):
                size += len(chunk)
                if size > remaining:
                    raise HTTPException(status_code=413, detail="Vídeo grande demais (max 300MB)")
                dst.write(chunk)
        return path, size
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.post("/api/v1/form", status_code=201)
async def form_upload(request: Request, video: UploadFile = File(...), modality: str = Form("run"),
                      view: str = Form("lateral"), video_frontal: Optional[UploadFile] = File(None),
                      svc: FormService = Depends(get_form_service),
                      auth: AuthService = Depends(get_auth_service)):
    """Recebe o vídeo, salva no filesystem e ENFILEIRA o processamento (motor Rust em
    background). Responde 'processing' na hora — o usuário pode fechar a página e voltar.
    `view` = 'lateral' | 'frontal' (conjunto de métricas por vista). `video_frontal` (opcional):
    SEGUNDO clipe filmado de frente — quando vem, a análise funde os dois planos e passa a medir
    queda pélvica + valgo de joelho; sem ele, comportamento idêntico ao de hoje. Liga ao usuário
    se logado (pra correlação com lesão); convidado fica anônimo."""
    user_id_val = None
    try:
        user_id_val = auth.me(bearer(request))["user_id"]
    except AuthError:
        pass   # convidado -> análise anônima (degrada gracioso)
    limit_request(request, "form-upload-auth" if user_id_val else "form-upload-guest",
                  limit=20 if user_id_val else 6, window_s=600)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > _MAX_VIDEO_BYTES + _MAX_MULTIPART_OVERHEAD:
        raise HTTPException(status_code=413, detail="Vídeo grande demais (max 300MB)")
    staged, frontal_staged = None, None
    try:
        staged, used = await _stage_upload(video, _MAX_VIDEO_BYTES)
        if video_frontal is not None:
            frontal_staged, _ = await _stage_upload(video_frontal, _MAX_VIDEO_BYTES - used)
    except Exception:
        if staged:
            staged.unlink(missing_ok=True)
        raise
    try:
        return svc.create_from_staged(
            staged, video.filename or "video.mp4", None, modality or "run", view or "lateral",
            user_id_val, frontal_path=frontal_staged,
            frontal_filename=(video_frontal.filename if video_frontal else "frontal.mp4")
            or "frontal.mp4")
    except QueueFullError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except BackendConfigurationError:
        # Falha de implantação (asset/manifest), não de input do atleta. Não expõe paths, hashes
        # internos ou a configuração do host na resposta HTTP.
        raise HTTPException(status_code=503, detail="Motor de análise indisponível; tente mais tarde.")
    finally:
        # No sucesso os arquivos já foram movidos; numa falha de promoção, remove o staging órfão.
        staged.unlink(missing_ok=True)
        if frontal_staged:
            frontal_staged.unlink(missing_ok=True)


@router.get("/api/v1/form")
def form_list(request: Request, svc: FormService = Depends(get_form_service),
              auth: AuthService = Depends(get_auth_service)):
    return svc.list(user_id(request, auth))


@router.get("/api/v1/form/progress")
def form_progress(request: Request, progress=Depends(get_form_progress_service),
                  auth: AuthService = Depends(get_auth_service)):
    """Evolução do próprio atleta; nunca mistura pessoas, modelos ou capturas incompatíveis."""
    return progress.get(user_id(request, auth))


@router.get("/api/v1/form/{analysis_id}")
def form_get(analysis_id: str, request: Request, svc: FormService = Depends(get_form_service),
             auth: AuthService = Depends(get_auth_service)):
    ensure_uuid(analysis_id)
    row = svc.get_authorized(analysis_id, optional_user_id(request, auth), analysis_token(request))
    if row is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    return row


@router.get("/api/v1/form/{analysis_id}/video")
def form_video(analysis_id: str, request: Request, svc: FormService = Depends(get_form_service),
               auth: AuthService = Depends(get_auth_service)):
    """Serve o overlay.mp4 (esqueleto desenhado) direto do filesystem."""
    ensure_uuid(analysis_id)
    path = svc.authorized_video_path(analysis_id, optional_user_id(request, auth),
                                     analysis_token(request))
    if not path:
        raise HTTPException(status_code=404, detail="Vídeo não disponível")
    return FileResponse(path, media_type="video/mp4")


@router.post("/api/v1/form/{analysis_id}/coach")
def form_coach(analysis_id: str, request: Request,
               form: FormService = Depends(get_form_service),
               coach: FormCoach = Depends(get_form_coach),
               profiles: ProfileService = Depends(get_profile_service),
               auth: AuthService = Depends(get_auth_service)):
    """Algoritmo Corretivo: das métricas do vídeo -> plano de correção com exercícios citados.
    Usa o perfil do usuário logado (se houver) pra personalizar os alvos."""
    ensure_uuid(analysis_id)
    actor_id = optional_user_id(request, auth)
    capability = analysis_token(request)
    row = form.get_authorized(analysis_id, actor_id, capability)
    if row is None or row.get("metrics") is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada ou ainda sem métricas")
    profile, history = None, None
    try:
        uid = actor_id if not capability else None
        if not uid:
            raise AuthError(401, "convidado")
        profile = profiles.get(uid)
        history = injury_history(uid)   # lesão prévia sensibiliza o risco (preditor #1)
    except AuthError:
        pass   # sem login -> alvos populacionais + sem histórico (degrada gracioso)
    return {"analysis_id": analysis_id,
            **coach.plan(row["metrics"], profile=profile, history=history)}


@router.post("/api/v1/form/{analysis_id}/shoe")
def form_shoe(analysis_id: str, request: Request, cover: bool = False,
              form: FormService = Depends(get_form_service),
              recommender=Depends(get_shoe_recommender),
              profiles: ProfileService = Depends(get_profile_service),
              auth: AuthService = Depends(get_auth_service)):
    """Recomendação de tênis (EPIC D): pisada + oscilação (métricas do vídeo) + peso (perfil) +
    histórico de lesão (logado) → faixa de amortecimento/drop honesta e citada. `cover=1` pede a
    capa humana pelo LLM. Espelha o padrão do /coach; degrada gracioso sem login."""
    ensure_uuid(analysis_id)
    actor_id = optional_user_id(request, auth)
    capability = analysis_token(request)
    row = form.get_authorized(analysis_id, actor_id, capability)
    if row is None or row.get("metrics") is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada ou ainda sem métricas")
    # Sanitiza como o coach/plano: métrica impossível (ex.: oscilação vertical 24,7% = artefato)
    # NÃO pode virar conselho de tênis — o shoe é consumidor e trava o dado igual aos irmãos.
    metrics, _ = sanitize_metrics(row["metrics"])
    weight_kg, history = None, None
    try:
        uid = actor_id if not capability else None
        if not uid:
            raise AuthError(401, "convidado")
        weight_kg = (profiles.get(uid) or {}).get("weight_kg")
        history = injury_history(uid)   # lesão prévia por região ajusta o drop
    except AuthError:
        pass   # sem login -> só pisada/oscilação (degrada gracioso)
    rec = recommender.recommend(
        foot_strike=metrics.get("foot_strike"),
        vertical_oscillation_pct=metrics.get("vertical_oscillation_pct"),
        weight_kg=weight_kg, history=history, write_cover=cover)
    return {"analysis_id": analysis_id, **rec}


@router.post("/api/v1/form/{analysis_id}/plan")
def generate_plan(analysis_id: str, request: Request, weeks: int = 6,
                  form: FormService = Depends(get_form_service),
                  profiles: ProfileService = Depends(get_profile_service),
                  plans=Depends(get_plan_service),
                  auth: AuthService = Depends(get_auth_service)):
    """Plano corretivo de N semanas a partir da análise: desvios+risco+histórico → programa
    faseado citado. Usa `goal_timeframe_weeks` do perfil se `weeks` não vier. Persiste p/ logado."""
    ensure_uuid(analysis_id)
    actor_id = optional_user_id(request, auth)
    capability = analysis_token(request)
    row = form.get_authorized(analysis_id, actor_id, capability)
    if row is None or row.get("metrics") is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada ou ainda sem métricas")
    profile, history, uid = None, None, None
    try:
        uid = actor_id if not capability else None
        if not uid:
            raise AuthError(401, "convidado")
        profile = profiles.get(uid)
        history = injury_history(uid)
    except AuthError:
        pass
    weeks = (profile or {}).get("goal_timeframe_weeks") or weeks   # prazo do atleta, se houver
    plan = plan_from_metrics(row["metrics"], weeks=weeks, profile=profile, history=history)
    if uid and not plan.get("unreliable"):
        plans.create(uid, analysis_id, plan)   # persiste o histórico de planos do atleta
    return {"analysis_id": analysis_id, "plan": plan}


@router.get("/api/v1/plans")
def list_plans(request: Request, plans=Depends(get_plan_service),
               auth: AuthService = Depends(get_auth_service)):
    """Planos corretivos gerados pelo atleta logado (mais recentes primeiro = progressão)."""
    return plans.list(user_id(request, auth))
