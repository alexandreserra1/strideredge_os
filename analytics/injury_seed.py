"""analytics/injury_seed.py — ingere exemplos sintéticos COMO SE FOSSEM usuários (pipeline real).

Popula `form_analyses` (biomecânica) + `injury_reports` (lesão) com exemplos do gerador
(`injury_synth`, parametrizado pela literatura), pra provar o fluxo REAL fim-a-fim: seed →
`build_training_set` → `RiskModel`. Lesionado ganha uma lesão + análise ANTES do onset; saudável
ganha só análise (é o negativo do classificador).

HONESTIDADE: cada linha é marcada `user_id = 'synthetic-…'` — removível (`clear_synthetic`) e
NUNCA se passa por usuário real em produção. É andaime de treino/prova, não outcome de gente.
"""

import json
import uuid
from datetime import date, timedelta

from analytics.injury_synth import generate
from analytics.injury_taxonomy import DIAGNOSES

SYNTHETIC_PREFIX = "synthetic-"


def clear_synthetic(con) -> None:
    """Remove tudo que foi semeado (marcado pelo prefixo). Idempotente."""
    like = SYNTHETIC_PREFIX + "%"
    con.execute("DELETE FROM injury_reports WHERE user_id LIKE ?", [like])
    con.execute("DELETE FROM form_analyses WHERE user_id LIKE ?", [like])


def seed(con, n: int = 400, seed_val: int = 42, window_weeks: int = 8) -> dict:
    """Semeia `n` usuários sintéticos. Devolve contagem {injured, healthy}."""
    clear_synthetic(con)
    onset = date(2026, 6, 1)
    before = onset - timedelta(weeks=window_weeks // 2)   # análise dentro da janela pré-onset
    injured = 0
    for ex in generate(n=n, seed=seed_val):
        uid = SYNTHETIC_PREFIX + str(uuid.uuid4())
        _insert_analysis(con, uid, ex["features"], before if ex["label"] else onset)
        if ex["label"]:
            _insert_injury(con, uid, ex["diagnosis"], onset)
            injured += 1
    return {"injured": injured, "healthy": n - injured}


def _insert_analysis(con, uid: str, features: dict, when: date) -> None:
    con.execute(
        "INSERT INTO form_analyses (analysis_id, status, metrics, user_id, created_at) "
        "VALUES (?, 'done', ?, ?, ?)",
        [str(uuid.uuid4()), json.dumps(features), uid, when])


def _insert_injury(con, uid: str, diagnosis: str, onset: date) -> None:
    region = DIAGNOSES[diagnosis]["region"]
    con.execute(
        "INSERT INTO injury_reports (id, user_id, region, diagnosis, onset_date, q_pain) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [str(uuid.uuid4()), uid, region, diagnosis, onset, 2])
