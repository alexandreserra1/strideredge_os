"""api/profile.py — perfil do atleta (morfologia/hábitos) p/ personalizar a biomecânica.

Um registro por usuário. Usado por `analytics.biomechanics.ideal_targets` pra ajustar os
alvos (ex.: cadência-alvo escala com a altura). Tudo opcional: sem perfil, defaults valem.
"""

from typing import Optional

from core.database import get_connection

_FIELDS = ("height_cm", "weight_kg", "years_running", "goal")


class ProfileService:
    def get(self, user_id: str) -> Optional[dict]:
        row = get_connection().execute(
            "SELECT height_cm, weight_kg, years_running, goal FROM athlete_profile WHERE user_id = ?",
            [user_id]).fetchone()
        if row is None:
            return None
        return dict(zip(_FIELDS, row))

    def upsert(self, user_id: str, data: dict) -> dict:
        """Grava/atualiza o perfil (só os campos conhecidos). Idempotente por user_id."""
        clean = {k: data.get(k) for k in _FIELDS}
        get_connection().execute(
            """INSERT INTO athlete_profile (user_id, height_cm, weight_kg, years_running, goal, updated_at)
               VALUES (?, ?, ?, ?, ?, now())
               ON CONFLICT (user_id) DO UPDATE SET
                 height_cm=excluded.height_cm, weight_kg=excluded.weight_kg,
                 years_running=excluded.years_running, goal=excluded.goal, updated_at=now()""",
            [user_id, clean["height_cm"], clean["weight_kg"], clean["years_running"], clean["goal"]])
        return clean
