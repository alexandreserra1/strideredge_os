"""analytics/strength.py — séries de força e grupos musculares trabalhados.

O Garmin grava exercício/reps/peso por série SÓ no modo Força (memória do projeto).
O mapa exercício -> músculos é nosso (categorias FIT mais comuns); categoria fora
do mapa degrada gracioso ('outros').
"""

from core.database import get_connection

# categoria FIT -> grupos musculares primários (pt-BR)
EXERCISE_MUSCLES = {
    "bench_press": ["peito", "tríceps", "ombro"],
    "push_up": ["peito", "tríceps", "core"],
    "shoulder_press": ["ombro", "tríceps"],
    "lateral_raise": ["ombro"],
    "squat": ["quadríceps", "glúteo", "core"],
    "leg_press": ["quadríceps", "glúteo"],
    "lunge": ["quadríceps", "glúteo"],
    "deadlift": ["posterior de coxa", "glúteo", "lombar"],
    "hip_raise": ["glúteo", "posterior de coxa"],
    "leg_curl": ["posterior de coxa"],
    "calf_raise": ["panturrilha"],
    "pull_up": ["costas", "bíceps"],
    "lat_pulldown": ["costas", "bíceps"],
    "row": ["costas", "bíceps"],
    "curl": ["bíceps"],
    "triceps_extension": ["tríceps"],
    "plank": ["core"],
    "crunch": ["core"],
    "sit_up": ["core"],
    "total_body": ["corpo inteiro"],
}


class StrengthSets:
    """Leitura das séries de um treino + resumo de músculos (conclusão-pronta p/ UI e coach)."""

    def sets(self, activity_id: str) -> list:
        rows = get_connection().execute(
            """SELECT set_index, exercise, reps, weight_kg, duration_s
               FROM fact_strength_sets WHERE activity_id = ? ORDER BY set_index""",
            [activity_id]).fetchall()
        return [{"set_index": r[0], "exercise": r[1], "reps": r[2],
                 "weight_kg": r[3], "duration_s": r[4]} for r in rows]

    def summary(self, activity_id: str) -> dict:
        """{sets, muscles: [{muscle, sets}]} — músculos ordenados por volume de séries."""
        sets = self.sets(activity_id)
        counts: dict = {}
        for st in sets:
            for m in EXERCISE_MUSCLES.get(st["exercise"] or "", ["outros"]):
                counts[m] = counts.get(m, 0) + 1
        muscles = [{"muscle": m, "sets": n}
                   for m, n in sorted(counts.items(), key=lambda kv: -kv[1])]
        return {"sets": sets, "muscles": muscles}
