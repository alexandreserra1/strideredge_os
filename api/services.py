"""api/services.py — camada de serviço (OOP) por trás da API.

Os endpoints ficam finos; a lógica vive em classes de serviço. ActivityService
COMPÕE os analyzers (polimorfismo) — adicionar análise nova não muda os endpoints.
"""

from typing import Optional

from core.database import get_connection
from analytics.run_analysis import BreakingPointAnalyzer, EfficiencyAnalyzer, DurabilityAnalyzer
from analytics.intensity import HrZoneAnalyzer
from analytics.processors import smooth_track, cadence_analysis


class ActivityService:
    """Leitura e detalhe de atividades para a API."""

    def __init__(self):
        self.breaking = BreakingPointAnalyzer()
        self.efficiency = EfficiencyAnalyzer()
        self.durability = DurabilityAnalyzer()
        self.zones = HrZoneAnalyzer()

    def list(self) -> list:
        con = get_connection()
        rows = con.execute(
            """SELECT activity_id, activity_name, primary_type, start_time,
                      total_distance_meters, total_duration_seconds
               FROM dim_activities ORDER BY start_time DESC"""
        ).fetchall()
        cols = ["activity_id", "activity_name", "primary_type", "start_time", "distance_m", "duration_s"]
        out = []
        for r in rows:
            d = dict(zip(cols, r))
            d["activity_id"] = str(d["activity_id"])
            out.append(d)
        return out

    def detail(self, activity_id: str) -> Optional[dict]:
        con = get_connection()
        meta = con.execute(
            """SELECT a.activity_name, a.primary_type, a.total_distance_meters,
                      a.total_duration_seconds, c.avg_hr, c.avg_cadence
               FROM dim_activities a
               LEFT JOIN cache_workout_summary c ON c.activity_id = a.activity_id
               WHERE a.activity_id = ?""",
            [activity_id],
        ).fetchone()
        if meta is None:
            return None
        name, ptype, dist, dur, avg_hr, avg_cad = meta
        return {
            "activity_id": activity_id,
            "name": name, "type": ptype,
            "distance_m": dist, "duration_s": dur,
            "avg_hr": avg_hr, "avg_cadence": avg_cad,
            "breaking_point": self.breaking.analyze(activity_id),
            "efficiency": self.efficiency.analyze(activity_id),
            "durability": self.durability.analyze(activity_id),
            "hr_zones": self.zones.analyze(activity_id),
        }

    def track(self, activity_id: str) -> dict:
        return smooth_track(activity_id)

    def telemetry(self, activity_id: str) -> list:
        """Série temporal completa (para os gráficos do cliente). gzip cuida do tamanho."""
        con = get_connection()
        rows = con.execute(
            """SELECT timestamp, heart_rate, cadence, altitude, speed_ms
               FROM fact_telemetry WHERE activity_id = ? ORDER BY timestamp""",
            [activity_id],
        ).fetchall()
        cols = ["timestamp", "heart_rate", "cadence", "altitude", "speed_ms"]
        return [dict(zip(cols, r)) for r in rows]

    def spectrum(self, activity_id: str) -> dict:
        return cadence_analysis(activity_id)
