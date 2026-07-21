"""api/plans.py — persistência dos planos corretivos gerados (espelha ProfileService/InjuryService).

Um registro por plano gerado, ligado ao atleta e à análise de origem. O plano em si (JSON) vem
de `analytics.training_plan`; aqui só guardamos/lemos. Re-gerar por novo vídeo = novo registro
(o histórico de planos mostra a progressão do atleta).
"""

import json
import uuid
from typing import Optional

from core.database import get_connection

_COLS = "id, user_id, analysis_id, weeks, plan, created_at"


class PlanService:
    def create(self, user_id: str, analysis_id: Optional[str], plan: dict) -> dict:
        pid = str(uuid.uuid4())
        get_connection().execute(
            "INSERT INTO training_plans (id, user_id, analysis_id, weeks, plan) "
            "VALUES (?, ?, ?, ?, ?)",
            [pid, user_id, analysis_id, plan.get("duration_weeks"), json.dumps(plan)])
        return self.get(pid)

    def get(self, plan_id: str) -> Optional[dict]:
        row = get_connection().execute(
            f"SELECT {_COLS} FROM training_plans WHERE id = ?", [plan_id]).fetchone()
        return self._row(row) if row else None

    def list(self, user_id: str) -> list:
        rows = get_connection().execute(
            f"SELECT {_COLS} FROM training_plans WHERE user_id = ? ORDER BY created_at DESC",
            [user_id]).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r) -> dict:
        return {"id": str(r[0]), "user_id": r[1], "analysis_id": str(r[2]) if r[2] else None,
                "weeks": r[3], "plan": json.loads(r[4]) if r[4] else None,
                "created_at": str(r[5])}
