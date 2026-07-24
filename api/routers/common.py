"""api/routers/common.py — helpers compartilhados pelos routers (controllers finos).

Regra do projeto: o controller valida entrada e delega ao serviço; a regra de negócio mora nas
classes de serviço. Estes helpers só traduzem borda HTTP (UUID inválido → 404, AuthError → status
do serviço) e extraem o token — reusados por todos os routers pra não repetir."""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, Request

from api.auth import AuthError, AuthService
from core.rate_limit import rate_limiter


def ensure_uuid(value: str) -> None:
    """String que não é UUID = 404 (não 500)."""
    try:
        UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail="Não encontrado")


def auth_call(fn, *args):
    """Traduz AuthError -> HTTPException (controllers finos, regra no serviço)."""
    try:
        return fn(*args)
    except AuthError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


def bearer(request: Request) -> str:
    """Extrai o token do header Authorization: Bearer <token> (vazio se ausente)."""
    return (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()


def user_id(request: Request, auth: AuthService) -> str:
    """user_id do atleta logado; 401/erro via auth_call se o token for inválido/ausente."""
    return auth_call(auth.me, bearer(request))["user_id"]


def optional_user_id(request: Request, auth: AuthService) -> Optional[str]:
    """Sessão opcional para recursos que também suportam convidado por capability."""
    try:
        return auth.me(bearer(request))["user_id"]
    except AuthError:
        return None


def analysis_token(request: Request) -> str:
    """Capability de análise anônima; não é aceita na URL para não vazar em logs/referrers."""
    return (request.headers.get("x-analysis-token") or "").strip()


def limit_request(request: Request, bucket: str, limit: int, window_s: int) -> None:
    """Limita pelo peer TCP, não por headers forjáveis. O proxy de produção deve preservar o IP real."""
    peer = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(f"{bucket}:{peer}", limit, window_s):
        raise HTTPException(status_code=429, detail="Muitas tentativas; aguarde e tente novamente.",
                            headers={"Retry-After": str(window_s)})
