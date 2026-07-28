"""core/database.py — conexao reutilizavel com o DuckDB e migracoes.

Tudo que toca o banco passa por aqui. Mantemos UMA conexao-RAIZ por processo
(reutilizada), em vez de abrir/fechar a cada consulta — menos overhead e codigo
mais limpo. DuckDB e single-writer; uma conexao read-write le e escreve.

THREAD-SAFETY: a conexao do DuckDB NAO e thread-safe. A API (FastAPI) atende
requisicoes em threadpool — o navegador dispara varias em paralelo — e usar a
mesma conexao de 2 threads derruba o processo (crash nativo, SIGTRAP). O jeito
sancionado pelo DuckDB e: UMA conexao-raiz + um CURSOR por thread (cursor()
compartilha o mesmo banco/catalogo e tem a mesma API). get_connection() devolve
o cursor da thread atual — quem chama nao muda nada.
"""

import os
import threading
from pathlib import Path
import duckdb

# Raiz do projeto = duas pastas acima deste arquivo (core/database.py -> projeto).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "storage" / "strideredge.db"
MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"

# Conexao-raiz compartilhada (uma por processo) + cursores por thread.
# _generation invalida cursores antigos quando a raiz e fechada/reaberta (testes).
_connection = None
_generation = 0
_local = threading.local()


def restrict_permissions(path: Path, mode: int) -> None:
    """Best-effort POSIX hardening; não impede execução em plataformas sem chmod útil."""
    try:
        path.chmod(mode)
    except OSError:
        pass


def _resolve_db_path() -> str:
    """Caminho do banco. STRIDEREDGE_DB permite os testes usarem um banco temporario."""
    return os.environ.get("STRIDEREDGE_DB", str(DB_PATH))


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Devolve o handle reutilizavel do banco DESTA thread. NAO feche — e compartilhado.

    Por baixo: uma unica conexao-raiz por processo; cada thread recebe um cursor()
    dela (mesma API, mesmo banco), porque a conexao nao e thread-safe. O parametro
    read_only e mantido por compatibilidade de assinatura.
    """
    global _connection
    if _connection is None:
        path = _resolve_db_path()
        db_file = Path(path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        restrict_permissions(db_file.parent, 0o700)
        _connection = duckdb.connect(path)
        restrict_permissions(db_file, 0o600)
        restrict_permissions(Path(f"{path}.wal"), 0o600)
    if getattr(_local, "gen", None) != _generation or getattr(_local, "cursor", None) is None:
        _local.cursor = _connection.cursor()
        _local.gen = _generation
    return _local.cursor


def close_connection(timeout: float = 5.0) -> None:
    """Fecha a conexao-raiz compartilhada (shutdown da API e testes/teardown). CHECKPOINT antes de
    fechar FORCA o flush do WAL pro arquivo .db: sem isso, um WAL orfao sobra e o replay dele no
    proximo boot dispara um erro interno do DuckDB -> a API nao sobe (bug real em restarts).

    BOUNDED: se um job de fundo ainda segura um cursor, o CHECKPOINT/close pode BLOQUEAR
    indefinidamente e pendurar o SIGTERM. Por isso rodamos o checkpoint+close numa thread e
    damos join(timeout): se estourar, desistimos gracioso (loga e segue). O pior caso vira
    "WAL sobra e e recuperado no proximo boot" — ruim, mas MELHOR que travar o encerramento.
    No caminho feliz (nada segurando a conexao) o checkpoint e rapido e termina bem antes do
    timeout, preservando o comportamento anti-corrupcao de sempre."""
    global _connection, _generation
    con = _connection
    if con is not None:
        def _checkpoint_and_close():
            try:
                con.execute("CHECKPOINT")
            except Exception:   # noqa: BLE001 — best-effort; conexao ja fechada/read-only nao impede o resto
                pass
            try:
                con.close()
            except Exception:   # noqa: BLE001
                pass

        t = threading.Thread(target=_checkpoint_and_close, name="db-checkpoint-close", daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            # Nao terminou no prazo: algum worker ainda segura a conexao. Nao esperamos mais —
            # abandonamos a thread (daemon) e seguimos. O WAL fica orfao e sera recuperado no boot.
            # Import tardio: core.logging importa core.database (evita ciclo no topo do modulo).
            from core.logging import Logger
            Logger("database").warning("db_close_timeout", timeout=timeout)
        _connection = None
    _generation += 1          # invalida os cursores cacheados de TODAS as threads
    _local.cursor = None


def run_migrations(con: duckdb.DuckDBPyConnection) -> list:
    """Roda todos os .sql de db/migrations/ em ordem alfabetica (IF NOT EXISTS)."""
    applied = []
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        con.execute(sql_file.read_text())
        applied.append(sql_file.name)
    return applied
