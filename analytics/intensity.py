"""analytics/intensity.py — distribuicao de FC por zona (intensidade do treino).

Usa as zonas que o PROPRIO Garmin calculou (gravadas em dim_activities a partir
do .FIT): limites reais configurados pelo atleta e tempo em cada faixa. Sem
estimativa nossa — dado fiel.

Implementa BaseAnalyzer (mesmo contrato de toda analise de treino), entao o Coach
pode reuni-lo junto com os outros de forma polimorfica.
"""

from typing import Optional

from core.database import get_connection
from core.framework.interfaces import BaseAnalyzer


class HrZoneAnalyzer(BaseAnalyzer):
    """Quanto tempo (%) o atleta passou em cada faixa de FC, segundo o Garmin."""

    label = "Zonas de FC"

    @staticmethod
    def _zone_label(boundaries: list, i: int) -> str:
        """Rotulo da faixa i. Ha 7 faixas para 6 limites (abaixo da 1a e acima da ultima)."""
        if i == 0:
            return f"<{boundaries[0]}"
        if i >= len(boundaries):
            return f">{boundaries[-1]}"
        return f"{boundaries[i - 1]}-{boundaries[i]}"

    def analyze(self, activity_id: str) -> dict:
        con = get_connection()
        row = con.execute(
            "SELECT hr_zone_boundaries, hr_zone_seconds FROM dim_activities WHERE activity_id = ?",
            [activity_id],
        ).fetchone()

        if not row or not row[0] or not row[1]:
            return {"hr_max": None, "zones": []}

        boundaries, seconds = row[0], row[1]
        total = sum(seconds) or 1
        zones = [
            {
                "faixa": self._zone_label(boundaries, i),
                "segundos": round(sec),
                "pct": round(100 * sec / total, 1),
            }
            for i, sec in enumerate(seconds)
            if sec > 0
        ]
        result = {"hr_max": boundaries[-1], "zones": zones}
        # Faixas REAIS do atleta a partir dos MESMOS limites (sem query/calculo extra):
        # buckets <b0 | b0-b1 Z1 | b1-b2 Z2 | b2-b3 Z3 | b3-b4 Z4 | b4-b5 Z5.
        if len(boundaries) >= 4:
            result.update(z2_low=boundaries[1], z2_high=boundaries[2], hard_from=boundaries[3])
        return result

    def to_prompt(self, result: dict) -> Optional[str]:
        if not result["zones"]:
            return None
        dist = ", ".join(f"{z['faixa']} bpm: {z['pct']}%" for z in result["zones"])
        linha = f"FC maxima real do atleta: {result['hr_max']}. Tempo por faixa de FC: {dist}."
        if result.get("z2_low"):  # da ao coach o NUMERO real para recomendar intensidade
            linha += (f" Faixas reais do atleta (cite estes numeros ao recomendar intensidade, "
                      f"NAO invente): Zona 2 / base aerobica (ritmo leve) = "
                      f"{result['z2_low']}-{result['z2_high']} bpm; forte = acima de {result['hard_from']} bpm.")
        return linha


if __name__ == "__main__":
    analyzer = HrZoneAnalyzer()
    con = get_connection()
    acts = con.execute("SELECT activity_id, activity_name FROM dim_activities").fetchall()
    for aid, name in acts:
        r = analyzer.analyze(aid)
        line = analyzer.to_prompt(r)
        print(f"{name:18}: {line or 'sem dados de zona no .FIT'}")
