"""core/repository.py — fronteira de acesso a dado (leituras compartilhadas).

Centraliza a UMA forma de query que se repetia em vários analisadores:
    SELECT <colunas> FROM fact_telemetry WHERE activity_id = ? [AND <col> IS NOT NULL]
    ORDER BY timestamp
Assim, um `ALTER TABLE` de coluna mexe num lugar só. As queries analiticas UNICAS
(CTEs, GROUP BY, janelas de ACWR) continuam no analisador — forcar TODAS pra ca seria
overengineering (constituicao S2). Usa a conexao unica (get_connection).

REGRA DE SEGURANCA: `columns`/`non_null` vem SEMPRE de codigo (nunca de input do
usuario) e sao validadas contra a lista de colunas conhecidas de fact_telemetry.
"""

from typing import List, Optional, Sequence

from core.database import get_connection

# colunas reais de fact_telemetry (defesa em profundidade — nada de coluna arbitraria no SQL)
_TELEMETRY_COLUMNS = {
    "telemetry_id", "activity_id", "user_id", "device_id", "timestamp",
    "heart_rate", "cadence", "latitude", "longitude", "altitude",
    "vertical_oscillation", "stance_time_ms", "speed_ms", "distance_m",
}


class TelemetryRepository:
    """Leituras da fact_telemetry. A serie sempre volta ORDER BY timestamp."""

    def series(self, activity_id: str, columns: Sequence[str],
               non_null: Optional[str] = None) -> List[tuple]:
        """Serie temporal de `columns` de um treino, em ordem cronologica.

        non_null: filtra linhas onde essa coluna e NULL (ex.: so pontos com GPS).
        """
        cols = list(columns)
        unknown = set(cols) | ({non_null} if non_null else set())
        unknown -= _TELEMETRY_COLUMNS
        if unknown:
            raise ValueError(f"coluna(s) desconhecida(s) em fact_telemetry: {sorted(unknown)}")

        sql = f"SELECT {', '.join(cols)} FROM fact_telemetry WHERE activity_id = ?"
        if non_null:
            sql += f" AND {non_null} IS NOT NULL"
        sql += " ORDER BY timestamp"
        return get_connection().execute(sql, [activity_id]).fetchall()

    def column(self, activity_id: str, column: str) -> List[float]:
        """Uma coluna numerica (nao-nula) como lista de floats — atalho comum."""
        rows = self.series(activity_id, [column], non_null=column)
        return [float(r[0]) for r in rows]
