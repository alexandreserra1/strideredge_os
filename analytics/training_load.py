"""analytics/training_load.py — carga de treino (TRIMP ponderado por zona) e ACWR.

Trilha 1: transforma treinos soltos em métricas de carga e risco de lesão.

- CARGA (TRIMP de Edwards): soma do tempo em cada zona de FC × peso da zona (zonas
  altas pesam mais). Usa as zonas REAIS do Garmin (hr_zone_seconds). Fallback p/
  treinos sem zona: duração × peso estimado da FC média.
- ACWR = carga aguda (média 7 dias) / crônica (média 28 dias). Com PORTÃO de
  confiança: nos primeiros ~28 dias (base crônica ainda se formando) o resultado é
  "aquecendo", não "risco" — evita falso alarme (como o Garmin, que esconde 2 semanas).
- Regra dos 10%: variação da carga aguda semana-a-semana = sinal precoce de risco.
"""

from datetime import timedelta
from typing import Optional

from core.database import get_connection
from core.framework.interfaces import BaseAnalyzer


class TrainingLoad:
    """Carga de treino (TRIMP ponderado por zona) e ACWR (com portão de confiança)."""

    # Pesos de Edwards por bucket de FC (7 buckets p/ 6 limites do Garmin):
    # abaixo-Z1, Z1, Z2, Z3, Z4, Z5, acima-Zmax. Zona alta pesa mais.
    EDWARDS_WEIGHTS = [1, 1, 2, 3, 4, 5, 5]
    CHRONIC_WINDOW_DAYS = 28

    @staticmethod
    def activity_trimp(zone_seconds, avg_hr, duration_min, hr_max: int = 198) -> float:
        """Carga (Edwards) de UM treino. Usa zonas do Garmin; senão estima por FC média."""
        weights = TrainingLoad.EDWARDS_WEIGHTS
        if zone_seconds and sum(zone_seconds) > 0:
            return round(sum((s / 60.0) * weights[min(i, len(weights) - 1)]
                             for i, s in enumerate(zone_seconds)), 1)
        if avg_hr and duration_min:
            frac = avg_hr / hr_max
            weight = 1 if frac < 0.6 else 2 if frac < 0.7 else 3 if frac < 0.8 else 4 if frac < 0.9 else 5
            return round(duration_min * weight, 1)
        return 0.0

    @staticmethod
    def acwr_status(acwr, days_of_history: int) -> str:
        """Zona do ACWR, com PORTÃO: histórico curto = 'aquecendo' (não confiável)."""
        if days_of_history < TrainingLoad.CHRONIC_WINDOW_DAYS:
            return "aquecendo"
        if acwr is None:
            return "sem dados"
        if acwr < 0.8:
            return "destreino"
        if acwr <= 1.3:
            return "zona segura"
        if acwr <= 1.5:
            return "atencao"
        return "risco de lesao"

    def refresh_cache(self) -> int:
        """(Re)calcula os agregados por treino em cache_workout_summary (única varredura
        da fact_telemetry). Reconstrói do zero p/ não acumular órfãos."""
        con = get_connection()
        con.execute("DELETE FROM cache_workout_summary")
        con.execute(
            """INSERT INTO cache_workout_summary (activity_id, avg_hr, max_hr, avg_cadence)
               SELECT activity_id, AVG(heart_rate), MAX(heart_rate), AVG(cadence)
               FROM fact_telemetry WHERE heart_rate IS NOT NULL
               GROUP BY activity_id"""
        )
        return con.execute("SELECT COUNT(*) FROM cache_workout_summary").fetchone()[0]

    def _activity_rows(self) -> list:
        con = get_connection()
        return con.execute(
            """SELECT CAST(a.start_time AS DATE), a.activity_name, a.primary_type,
                      a.total_duration_seconds / 60.0, c.avg_hr, a.hr_zone_seconds
               FROM dim_activities a
               LEFT JOIN cache_workout_summary c ON c.activity_id = a.activity_id
               WHERE a.total_duration_seconds IS NOT NULL
               ORDER BY a.start_time"""
        ).fetchall()

    def session_loads(self) -> list:
        return [
            {"activity_name": name, "primary_type": ptype, "day": day,
             "duration_min": dur, "avg_hr": hr, "trimp_load": self.activity_trimp(zs, hr, dur)}
            for day, name, ptype, dur, hr, zs in self._activity_rows()
        ]

    def acwr_timeline(self) -> list:
        """Carga diária + ACWR (com portão) + regra dos 10% (ramp semanal)."""
        daily = {}
        for day, _n, _t, dur, hr, zs in self._activity_rows():
            daily[day] = daily.get(day, 0.0) + self.activity_trimp(zs, hr, dur)
        if not daily:
            return []

        days = sorted(daily)
        first = days[0]
        acute_by_day, rows = {}, []
        for d in days:
            # janelas por TEMPO; dias sem treino contam carga 0 (por isso /7 e /28)
            acute = sum(v for k, v in daily.items() if d - timedelta(days=6) <= k <= d) / 7.0
            chronic = sum(v for k, v in daily.items() if d - timedelta(days=27) <= k <= d) / 28.0
            acute_by_day[d] = acute
            acwr = (acute / chronic) if chronic > 0 else None
            dh = (d - first).days
            rows.append({
                "day": d, "daily_load": round(daily[d], 1),
                "acute_7d": round(acute, 1), "chronic_28d": round(chronic, 1),
                "acwr": round(acwr, 2) if acwr is not None else None,
                "days_of_history": dh, "status": self.acwr_status(acwr, dh),
            })
        for r in rows:  # regra dos 10%: carga aguda de hoje vs. a de 7 dias atrás
            prev = acute_by_day.get(r["day"] - timedelta(days=7))
            r["ramp_pct"] = round(100 * (r["acute_7d"] - prev) / prev, 1) if prev and prev > 0 else None
        return rows

    def latest(self) -> Optional[dict]:
        """Estado de carga mais recente (o 'hoje' do atleta)."""
        tl = self.acwr_timeline()
        return tl[-1] if tl else None


class AcwrAnalyzer(BaseAnalyzer):
    """Estado de carga atual do atleta (ACWR) como contexto pro Coach — polimórfico.

    É métrica de atleta (não do treino), então ignora o activity_id e usa o estado mais
    recente. Adicionar ao Coach dá a ele a noção de risco de lesão por carga acumulada.
    """

    label = "Carga e prontidão (ACWR)"

    def analyze(self, activity_id: str) -> dict:
        return TrainingLoad().latest() or {}

    def to_prompt(self, result: dict) -> Optional[str]:
        if not result or result.get("acwr") is None:
            return None
        ramp = result.get("ramp_pct")
        ramp_txt = f"; carga semanal {ramp:+}%" if ramp is not None else ""
        return (f"Carga acumulada atual (ACWR): {result['acwr']} — {result['status']}{ramp_txt}. "
                f"(ACWR 0.8-1.3 = seguro; >1.5 = risco de lesao.)")


# Compatibilidade: callers antigos (conftest, sync) usam a função.
def refresh_summary_cache() -> int:
    return TrainingLoad().refresh_cache()


if __name__ == "__main__":
    tl = TrainingLoad()
    print(f"cache: {tl.refresh_cache()} treinos\n=== Linha do tempo ACWR ===")
    for r in tl.acwr_timeline():
        acwr = f"{r['acwr']:.2f}" if r["acwr"] is not None else "  - "
        ramp = f"{r['ramp_pct']:+.0f}%" if r["ramp_pct"] is not None else "   -"
        print(f"{r['day']}  carga={r['daily_load']:6.0f}  ACWR={acwr}  ramp={ramp:>5}  [{r['status']}]")
