"""api/main.py — Gateway REST do StriderEdge OS (FastAPI).

App focado em ANÁLISE DE FORMA POR VÍDEO (prevenção de lesão): auth, upload/consulta de análise
de forma, coach/tênis/plano corretivo citado, perfil e log de lesão. Os endpoints vivem em routers
por domínio (`api/routers/`) — aqui só montamos o app, o middleware e o ciclo de boot. Controllers
FINOS: validam entrada e delegam às classes de serviço injetadas via Depends. Processamento pesado
(motor de visão) roda em background pela fila de jobs — o request só enfileira e responde na hora.
"""

import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from core.logging import Logger
from api.deps import get_job_queue
from api.routers import auth, form, injuries, profile


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Boot da API: carrega o .env (credenciais Google), sobe o pool de workers da fila de
    jobs e recupera análises órfãs (crash: linhas 'processing' de quando o servidor caiu no
    meio do job de vídeo)."""
    from api.form import purge_expired_guest_analyses, recover_orphaned_analyses
    from core.database import get_connection, run_migrations
    from core.env import load_dotenv
    load_dotenv()
    run_migrations(get_connection())   # idempotente (IF NOT EXISTS) — schema sempre em dia no boot
    get_job_queue().start()
    recover_orphaned_analyses()
    purge_expired_guest_analyses()
    yield
    # Shutdown LIMPO e BOUNDED. Ordem importa: primeiro paramos a fila de jobs (workers largam a
    # conexao/cursor); so entao o CHECKPOINT — assim ninguem segura a raiz e o checkpoint e rapido.
    # Se um job estiver preso, stop()/close_connection() tem timeout e NAO penduram o SIGTERM.
    from core.database import close_connection
    try:
        get_job_queue().stop()
    except Exception:  # noqa: BLE001 — teardown best-effort; nunca pode impedir o resto do shutdown
        pass
    # CHECKPOINT + fecha o DuckDB pra o WAL nao ficar orfao. WAL orfao corrompe o replay no proximo
    # boot e a API nao sobe — bug real observado em restarts (inclusive SIGTERM).
    close_connection()


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
    # A API não renderiza HTML do usuário; estes headers reduzem exposição caso uma resposta seja
    # aberta no browser. A CSP da SPA em produção pertence também ao servidor estático/proxy.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy",
                                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
    return response


# Routers por domínio (mesmos paths /api/v1/... de sempre) — controllers finos.
app.include_router(auth.router)
app.include_router(form.router)
app.include_router(profile.router)
app.include_router(injuries.router)
