"""analytics/athlete.py — memória/personalização do atleta.

O coach deixa de ser genérico ao comparar o treino atual com o HISTÓRICO do
próprio atleta (cadência hoje vs. sua mediana, FC vs. sua média). É determinístico
(o código calcula; o LLM só redige) e implementa BaseAnalyzer — entra na lista do
Coach sem mexer no Coach.

Single-user agora: o histórico = todos os outros treinos em cache_workout_summary.
Multi-user (filtrar por user_id) é costura da Fase B.
"""

from typing import Optional

from core.database import get_connection
from core.framework.interfaces import BaseAnalyzer


class AthleteHistoryAnalyzer(BaseAnalyzer):
    """Compara o treino atual com o histórico do atleta (personalização)."""

    label = "Histórico do atleta"

    def analyze(self, activity_id: str) -> dict:
        con = get_connection()
        # baseline histórico = outros treinos do atleta (exclui o atual)
        hist = con.execute(
            """SELECT COUNT(*), MEDIAN(avg_cadence), AVG(avg_hr)
               FROM cache_workout_summary WHERE activity_id != ?""",
            [activity_id],
        ).fetchone()
        now = con.execute(
            "SELECT avg_cadence, avg_hr FROM cache_workout_summary WHERE activity_id = ?",
            [activity_id],
        ).fetchone()

        count = hist[0] if hist else 0
        return {
            "history_count": count,
            "cadence_median": round(hist[1]) if hist and hist[1] is not None else None,
            "hr_avg": round(hist[2]) if hist and hist[2] is not None else None,
            "cadence_now": round(now[0]) if now and now[0] is not None else None,
            "hr_now": round(now[1]) if now and now[1] is not None else None,
        }

    def to_prompt(self, result: dict) -> Optional[str]:
        if not result.get("history_count") or result.get("cadence_now") is None:
            return None
        partes = [f"Comparado ao seu histórico ({result['history_count']} treino(s) anteriores):"]
        if result.get("cadence_median"):
            diff = round(100 * (result["cadence_now"] - result["cadence_median"]) / result["cadence_median"], 1)
            partes.append(
                f"cadência média hoje {result['cadence_now']} spm vs. sua mediana "
                f"{result['cadence_median']} ({diff:+}%)"
            )
        if result.get("hr_avg") and result.get("hr_now") is not None:
            partes.append(f"FC média hoje {result['hr_now']} vs. sua média {result['hr_avg']} bpm")
        return " ".join(partes) + "."
