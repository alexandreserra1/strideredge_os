"""api/routers/injuries.py — log de lesão OSTRC (base do modelo de risco treinado)."""

from fastapi import APIRouter, Depends, HTTPException, Request

from analytics.injury_taxonomy import taxonomy_payload
from api.auth import AuthService
from api.injuries import InjuryError, InjuryService
from api.deps import get_auth_service, get_diagnosis_classifier, get_injury_service
from api.routers.common import user_id
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/injuries", tags=["injuries"])


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


@router.get("/taxonomy")
def injury_taxonomy():
    """Vocabulário controlado (região→diagnóstico→lado) pro picker do frontend. Público (só vocab)."""
    return taxonomy_payload()


@router.get("")
def list_injuries(request: Request, auth: AuthService = Depends(get_auth_service),
                  injuries: InjuryService = Depends(get_injury_service)):
    """Lesões reportadas pelo atleta logado (com severidade OSTRC computada)."""
    return injuries.list(user_id(request, auth))


@router.post("", status_code=201)
def log_injury(req: InjuryRequest, request: Request,
               auth: AuthService = Depends(get_auth_service),
               injuries: InjuryService = Depends(get_injury_service)):
    """Registra uma lesão (vocabulário controlado da taxonomia + 4 perguntas OSTRC)."""
    try:
        return injuries.log(user_id(request, auth), req.model_dump())
    except InjuryError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{injury_id}/classify")
def classify_injury(injury_id: str, request: Request,
                    auth: AuthService = Depends(get_auth_service),
                    injuries: InjuryService = Depends(get_injury_service),
                    classifier=Depends(get_diagnosis_classifier)):
    """Coach-time: mapeia o texto livre → diagnóstico da taxonomia (LLM, conjunto fechado +
    abstenção). Persiste só com confiança alta; do contrário mantém sem diagnóstico."""
    athlete_id = user_id(request, auth)
    report = injuries.classify(injury_id, athlete_id, classifier)
    if report is None:
        raise HTTPException(status_code=404, detail="lesão não encontrada")
    return report


@router.get("/{injury_id}/retrospective")
def injury_retrospective(injury_id: str, request: Request,
                         auth: AuthService = Depends(get_auth_service),
                         injuries: InjuryService = Depends(get_injury_service)):
    """Retrospecto honesto: cruza a lesão com os SINAIS biomecânicos que a literatura liga a ela,
    nas análises de forma do atleta ANTES do onset. Associação, não prova de causa."""
    out = injuries.retrospective(injury_id, user_id(request, auth))
    if out is None:
        raise HTTPException(status_code=404, detail="lesão não encontrada")
    return out
