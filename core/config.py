"""core/config.py — configuracao por AMBIENTE (padrao 12-factor).

Um lugar so pros flags de COMPORTAMENTO do backend.
"""

import os

ENV = os.environ.get("STRIDE_ENV", "development").strip().lower()
IS_PROD = ENV in ("production", "prod")


def summary() -> dict:
    """Config efetiva — logada no boot da API (boa pratica: o app declara como esta rodando)."""
    return {"env": ENV, "is_prod": IS_PROD}
