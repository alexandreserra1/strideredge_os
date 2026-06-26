"""core/database.py — conexao reutilizavel com o DuckDB e migracoes.

Tudo que toca o banco passa por aqui. Mantemos UMA conexao por processo
(reutilizada), em vez de abrir/fechar a cada consulta — menos overhead e codigo
mais limpo. DuckDB e single-writer; uma conexao read-write le e escreve.

Concorrencia entre varios processos (ex: dashboard + API ao mesmo tempo) e um
tema de Fase 2 (hospedado) — hoje o app roda em um processo por vez.
"""

from pathlib import Path
import duckdb

# Raiz do projeto = duas pastas acima deste arquivo (core/database.py -> projeto).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "storage" / "strideredge.db"
MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"

# Conexao compartilhada (uma por processo). Criada sob demanda na 1a chamada.
_connection = None


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Devolve a conexao reutilizavel (cria na 1a vez). NAO feche — e compartilhada.

    O parametro read_only e mantido por compatibilidade de assinatura; a conexao
    unica e read-write (le e escreve). Para encerrar de verdade use close_connection().
    """
    global _connection
    if _connection is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # garante a pasta storage/
        _connection = duckdb.connect(str(DB_PATH))
    return _connection


def close_connection() -> None:
    """Fecha a conexao compartilhada (uso em testes/teardown)."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def run_migrations(con: duckdb.DuckDBPyConnection) -> list:
    """Roda todos os .sql de db/migrations/ em ordem alfabetica (IF NOT EXISTS)."""
    applied = []
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        con.execute(sql_file.read_text())
        applied.append(sql_file.name)
    return applied
