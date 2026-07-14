"""Configuração dos testes — banco TEMPORÁRIO hermético.

Cada sessão de teste cria um DuckDB temporário e roda as migrations (auth_users,
form_analyses, athlete_profile). Sem dados semeados: os testes que precisam de linhas
as inserem e limpam sozinhos. Reproduzível em qualquer máquina / no CI.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session", autouse=True)
def _temp_db(tmp_path_factory):
    from core.database import close_connection, get_connection, run_migrations

    db_path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["STRIDEREDGE_DB"] = str(db_path)
    close_connection()  # descarta qualquer conexão ao banco real

    con = get_connection()
    run_migrations(con)   # cria auth_users, form_analyses, athlete_profile

    yield
    close_connection()
    os.environ.pop("STRIDEREDGE_DB", None)
