"""analytics/fitness.py — preditor de prova (Riegel) e tendência de fitness.

Fecha a Trilha 1 (carga): além do ACWR (risco), responde "quão rápido eu estou?"
e "estou evoluindo?".

- RACE PREDICTOR (fórmula de Riegel, 1981): a partir de UMA performance de referência
  (t1 sobre d1), projeta o tempo em outra distância: t2 = t1 * (d2/d1)^1.06. O expoente
  1.06 modela a perda de ritmo conforme a distância cresce (validado empiricamente).
  Mais preciso dentro de ~2x da distância de referência — por isso usamos como referência
  a MELHOR corrida real do atleta (não um sprint curto que infla a projeção do maratona).
- TENDÊNCIA DE FITNESS: eficiência = velocidade por batimento (m/s ÷ FC × 100). Sobe
  quando o atleta corre mais rápido com a mesma FC (proxy honesto de ganho aeróbico).
  Comparamos a média da metade recente vs. a antiga das corridas → melhorando/estável/caindo.
"""

from typing import Optional

from core.database import get_connection
from core.framework.interfaces import BaseAnalyzer
from analytics.run_analysis import metabolic_efficiency

# Distâncias-padrão de prova (km) — chave do dicionário é o rótulo.
STANDARD_RACES = {"5k": 5.0, "10k": 10.0, "21k (meia)": 21.0975, "42k (maratona)": 42.195}


class RunningFitness:
    """Preditor de prova (Riegel) e tendência de fitness a partir das corridas reais."""

    RIEGEL_EXPONENT = 1.06
    # Referência mínima: ignora intervalos/sprints curtos que distorceriam o Riegel.
    MIN_REFERENCE_M = 2000
    TREND_THRESHOLD = 0.03  # ±3% para sair de "estável"

    @staticmethod
    def riegel(t1_s: float, d1_m: float, d2_m: float, exponent: float = RIEGEL_EXPONENT) -> float:
        """Tempo (s) previsto na distância d2 a partir da performance (t1, d1)."""
        return t1_s * (d2_m / d1_m) ** exponent

    @staticmethod
    def trend_label(values: list) -> str:
        """Rótulo de tendência de uma série cronológica (metade antiga vs. recente)."""
        if len(values) < 4:
            return "dados insuficientes"
        h = len(values) // 2
        old = sum(values[:h]) / h
        new = sum(values[h:]) / (len(values) - h)
        if old == 0:
            return "dados insuficientes"
        change = (new - old) / old
        if change > RunningFitness.TREND_THRESHOLD:
            return "melhorando"
        if change < -RunningFitness.TREND_THRESHOLD:
            return "caindo"
        return "estavel"

    def _run_rows(self) -> list:
        """Corridas (RUN) com distância, duração e FC média, em ordem cronológica."""
        con = get_connection()
        return con.execute(
            """SELECT CAST(a.start_time AS DATE), a.activity_name,
                      a.total_distance_meters, a.total_duration_seconds, c.avg_hr
               FROM dim_activities a
               LEFT JOIN cache_workout_summary c ON c.activity_id = a.activity_id
               WHERE a.primary_type = 'RUN'
                 AND a.total_distance_meters > 0 AND a.total_duration_seconds > 0
               ORDER BY a.start_time"""
        ).fetchall()

    def reference(self) -> Optional[dict]:
        """Melhor corrida de referência: o melhor pace entre corridas >= 2km."""
        best = None
        for day, name, dist, dur, _hr in self._run_rows():
            if dist < self.MIN_REFERENCE_M:
                continue
            pace = dur / (dist / 1000.0)  # s/km — menor é melhor
            if best is None or pace < best["pace_s_km"]:
                best = {"day": day, "activity_name": name, "distance_m": dist,
                        "duration_s": dur, "pace_s_km": pace}
        return best

    def race_predictions(self, races: dict = STANDARD_RACES) -> dict:
        """Projeção de Riegel para as distâncias-padrão a partir da referência."""
        ref = self.reference()
        if ref is None:
            return {"reference": None, "predictions": []}
        preds = []
        for label, km in races.items():
            t2 = self.riegel(ref["duration_s"], ref["distance_m"], km * 1000.0)
            preds.append({"race": label, "distance_km": km, "time_s": round(t2),
                          "pace_s_km": round(t2 / km, 1)})
        return {"reference": ref, "predictions": preds}

    def efficiency_trend(self) -> dict:
        """Eficiência (velocidade por batimento) por corrida + rótulo de tendência."""
        points = []
        for day, name, dist, dur, hr in self._run_rows():
            if not hr or hr <= 0:
                continue
            efficiency = round(metabolic_efficiency(dist / dur, hr), 2)  # velocidade por batimento
            points.append({"day": day, "activity_name": name, "efficiency": efficiency})
        trend = self.trend_label([p["efficiency"] for p in points])
        return {"trend": trend, "points": points}

    def summary(self) -> dict:
        """Visão consolidada: previsões + tendência (o que a API/coach consomem)."""
        return {**self.race_predictions(), "fitness": self.efficiency_trend()}


class FitnessAnalyzer(BaseAnalyzer):
    """Estado de fitness do atleta (previsão de prova + tendência) como contexto pro Coach.

    Métrica de atleta (não do treino): ignora o activity_id e usa o estado atual.
    Dá ao coach a noção de "quão rápido" e "evoluindo ou não".
    """

    label = "Fitness e previsão de prova"

    def analyze(self, activity_id: str) -> dict:
        return RunningFitness().summary()

    def to_prompt(self, result: dict) -> Optional[str]:
        preds = result.get("predictions") if result else None
        if not preds:
            return None
        by = {p["race"]: p for p in preds}
        partes = []
        for label in ("5k", "10k"):
            p = by.get(label)
            if p:
                m, s = divmod(p["time_s"], 60)
                partes.append(f"{label} ~{m}:{s:02d}")
        trend = result.get("fitness", {}).get("trend")
        trend_txt = f"; fitness {trend}" if trend and trend != "dados insuficientes" else ""
        if not partes:
            return None
        return (f"Previsao de prova (Riegel, da melhor corrida): {', '.join(partes)}{trend_txt}. "
                f"(Estimativa estatistica, nao garante; mais precisa perto da distancia treinada.)")


if __name__ == "__main__":
    f = RunningFitness()
    res = f.race_predictions()
    ref = res["reference"]
    if ref:
        print(f"Referência: {ref['activity_name']} {ref['distance_m']/1000:.1f}km "
              f"@ {ref['pace_s_km']/60:.2f} min/km\n=== Previsões (Riegel) ===")
        for p in res["predictions"]:
            m, s = divmod(p["time_s"], 60)
            print(f"  {p['race']:16s} {m:3d}:{s:02d}  ({p['pace_s_km']/60:.2f} min/km)")
    print(f"\nTendência de fitness: {f.efficiency_trend()['trend']}")
