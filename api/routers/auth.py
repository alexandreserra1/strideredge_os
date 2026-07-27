"""api/routers/auth.py — contas (registro, login, Google, sessão)."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from api.auth import AuthService
from api.deps import get_auth_service
from api.routers.common import auth_call, bearer, limit_request

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleRequest(BaseModel):
    credential: str


@router.post("/register", status_code=201)
def auth_register(req: RegisterRequest, request: Request,
                  auth: AuthService = Depends(get_auth_service)):
    """Cadastro único por e-mail; senha vira PBKDF2+salt (nunca em claro)."""
    limit_request(request, "auth-register", limit=12, window_s=600)
    return auth_call(auth.register, req.name, req.email, req.password)


@router.post("/login")
def auth_login(req: LoginRequest, request: Request,
               auth: AuthService = Depends(get_auth_service)):
    limit_request(request, "auth-login", limit=20, window_s=600)
    return auth_call(auth.login, req.email, req.password)


@router.post("/google")
def auth_google(req: GoogleRequest, request: Request,
                auth: AuthService = Depends(get_auth_service)):
    """Login/cadastro com o ID token do Google (exige GOOGLE_CLIENT_ID no ambiente)."""
    limit_request(request, "auth-google", limit=12, window_s=600)
    return auth_call(auth.login_google, req.credential)


@router.get("/me")
def auth_me(request: Request, auth: AuthService = Depends(get_auth_service)):
    return auth_call(auth.me, bearer(request))
