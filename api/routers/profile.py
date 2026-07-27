"""api/routers/profile.py — perfil do atleta (personaliza os alvos biomecânicos)."""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from api.auth import AuthService
from api.profile import ProfileService
from api.deps import get_auth_service, get_profile_service
from api.routers.common import user_id

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


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


@router.get("")
def get_profile(request: Request, auth: AuthService = Depends(get_auth_service),
                profiles: ProfileService = Depends(get_profile_service)):
    """Perfil do atleta logado (morfologia/hábitos). {} se ainda não preenchido."""
    return profiles.get(user_id(request, auth)) or {}


@router.put("")
def put_profile(req: ProfileRequest, request: Request,
                auth: AuthService = Depends(get_auth_service),
                profiles: ProfileService = Depends(get_profile_service)):
    return profiles.upsert(user_id(request, auth), req.model_dump())
