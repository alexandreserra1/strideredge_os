"""api/profile.py — perfil do atleta (morfologia/hábitos) p/ personalizar a biomecânica.

Um registro por usuário. Usado por `analytics.biomechanics.ideal_targets` pra ajustar os
alvos (ex.: cadência-alvo escala com a altura). Tudo opcional: sem perfil, defaults valem.
"""

from typing import Optional

from core.database import get_connection

# Campos do perfil (morfologia + hábitos + metas de treino/tênis). SQL montado a partir daqui —
# adicionar campo = só estender a tupla (+ migração). Sem duplicar SELECT/INSERT por campo.
_FIELDS = ("height_cm", "weight_kg", "years_running", "goal",
           "goal_timeframe_weeks", "weekly_volume_km", "days_per_week",
           "current_shoe", "footstrike_pref")


class ProfileService:
    def get(self, user_id: str) -> Optional[dict]:
        cols = ", ".join(_FIELDS)
        row = get_connection().execute(
            f"SELECT {cols} FROM athlete_profile WHERE user_id = ?", [user_id]).fetchone()
        return dict(zip(_FIELDS, row)) if row is not None else None

    def upsert(self, user_id: str, data: dict) -> dict:
        """Grava/atualiza o perfil (só os campos conhecidos). Idempotente por user_id."""
        clean = {k: data.get(k) for k in _FIELDS}
        cols = ", ".join(_FIELDS)
        placeholders = ", ".join("?" for _ in _FIELDS)
        updates = ", ".join(f"{k}=excluded.{k}" for k in _FIELDS)
        get_connection().execute(
            f"""INSERT INTO athlete_profile (user_id, {cols}, updated_at)
                VALUES (?, {placeholders}, now())
                ON CONFLICT (user_id) DO UPDATE SET {updates}, updated_at=now()""",
            [user_id] + [clean[k] for k in _FIELDS])
        return clean
