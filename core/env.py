"""core/env.py — carrega o .env pro ambiente, sem dependência externa.

Usa setdefault: variáveis JÁ definidas no ambiente têm precedência sobre o .env
(padrão 12-factor). Gitignored. Chamado no boot da API (credenciais do Google login).
"""

import os

from core.database import PROJECT_ROOT


def load_dotenv() -> None:
    env = PROJECT_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))
