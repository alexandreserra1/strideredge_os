"""analytics/processors.py — orquestra o kernel Rust sobre os dados do DuckDB.

O resto da aplicacao (API, dashboard) chama estas funcoes de alto nivel e nao
precisa saber de parametros de Kalman nem de como falar com o Rust.
"""

import rust_kernel
from core.database import get_connection

# Calibracao padrao do filtro de Kalman para trilhas de GPS (graus, amostras 1s).
# q pequeno = confia no modelo de movimento; R = ruido tipico do GPS (~5m).
# Escolhidos empiricamente: ~63% de reducao de tremor com ~1.8m de desvio.
GPS_DT = 1.0
GPS_PROCESS_NOISE = 1e-11
GPS_MEASUREMENT_NOISE = 5e-9


def smooth_track(activity_id: str) -> dict:
    """Le a trilha de uma atividade e devolve as versoes crua e suavizada.

    Retorna um dict com listas paralelas, pronto para plotar (raw vs. smooth).
    """
    con = get_connection()
    rows = con.execute(
        """SELECT latitude, longitude, cadence FROM fact_telemetry
           WHERE activity_id = ? AND latitude IS NOT NULL
           ORDER BY timestamp""",
        [activity_id],
    ).fetchall()

    raw_lat = [r[0] for r in rows]
    raw_lon = [r[1] for r in rows]
    cadence = [r[2] for r in rows]  # alinhado aos pontos (p/ o semaforo de cadencia)

    # >>> fronteira Python -> Rust: a suavizacao pesada roda no kernel nativo <<<
    smooth_lat, smooth_lon = rust_kernel.smooth_gps(
        raw_lat, raw_lon, GPS_DT, GPS_PROCESS_NOISE, GPS_MEASUREMENT_NOISE
    )

    return {
        "activity_id": activity_id,
        "points": len(raw_lat),
        "raw": {"latitude": raw_lat, "longitude": raw_lon},
        "smooth": {"latitude": smooth_lat, "longitude": smooth_lon},
        "cadence": cadence,
    }


# Metricas que fazem sentido comparar entre dois treinos.
_COMPARABLE_METRICS = {"heart_rate", "cadence", "altitude"}


def compare_activities(activity_id_a: str, activity_id_b: str, metric: str = "heart_rate") -> dict:
    """Compara dois treinos por uma metrica usando DTW (no kernel Rust).

    Distancia menor = esforcos mais parecidos (ignorando descompasso de tempo).
    """
    if metric not in _COMPARABLE_METRICS:
        raise ValueError(f"metrica invalida: {metric}")

    con = get_connection()

    def load(activity_id: str) -> list[float]:
        rows = con.execute(
            f"""SELECT {metric} FROM fact_telemetry
                WHERE activity_id = ? AND {metric} IS NOT NULL
                ORDER BY timestamp""",
            [activity_id],
        ).fetchall()
        return [float(r[0]) for r in rows]

    series_a = load(activity_id_a)
    series_b = load(activity_id_b)

    # >>> fronteira Python -> Rust: o O(n*m) roda no kernel nativo <<<
    distance, path = rust_kernel.compare_efforts(series_a, series_b)

    return {
        "metric": metric,
        "points_a": len(series_a),
        "points_b": len(series_b),
        "dtw_distance": distance,
        "alignment_path": path,
    }


def cadence_analysis(activity_id: str, sample_rate_hz: float = 1.0) -> dict:
    """Analise espectral (FFT) da cadencia de um treino, via kernel Rust.

    Devolve o espectro (pra plotar) e a frequencia dominante da oscilacao de
    cadencia. Razao pico/media alta = ritmo de passada mais regular.
    """
    con = get_connection()
    cadence = [
        float(r[0])
        for r in con.execute(
            """SELECT cadence FROM fact_telemetry
               WHERE activity_id = ? AND cadence IS NOT NULL
               ORDER BY timestamp""",
            [activity_id],
        ).fetchall()
    ]

    # >>> fronteira Python -> Rust: a FFT roda no kernel nativo <<<
    frequencies, magnitudes, dominant = rust_kernel.cadence_spectrum(cadence, sample_rate_hz)

    return {
        "activity_id": activity_id,
        "points": len(cadence),
        "dominant_frequency_hz": dominant,
        "spectrum": {"frequencies": frequencies, "magnitudes": magnitudes},
    }
