"""core/ingest.py — grava a telemetria de um .FIT no DuckDB (idempotente).

Pipeline: arquivo .FIT -> FitParser -> DataFrame Polars -> fact_telemetry.
A idempotencia vem do garmin_activity_id (UNIQUE em dim_activities): se a
atividade ja foi importada, nao reprocessa.
"""

import uuid
from typing import Optional

from core.database import get_connection
from core.parsers.fit_parser import FitParser


def _derive_primary_type(sport: Optional[str], sub_sport: Optional[str]) -> str:
    """Traduz o esporte do .FIT para o nosso rotulo interno (primary_type).

    Codigos confirmados a partir de arquivos reais do relogio:
      running/generic         -> RUN
      hiit/generic            -> HIIT
      training/cardio_training -> CARDIO
      training/strength_training -> STRENGTH  (sport 'training' e ambiguo:
                                               o sub_sport e quem desempata)
    """
    if sport is None:
        return "UNKNOWN"

    # 'training' e ambiguo: o sub_sport diz se foi cardio ou forca.
    if sport == "training":
        sub_map = {"cardio_training": "CARDIO", "strength_training": "STRENGTH"}
        return sub_map.get(sub_sport, "TRAINING")

    mapping = {
        "running": "RUN",
        "cycling": "BIKE",
        "hiit": "HIIT",
        "fitness_equipment": "CARDIO",
    }
    return mapping.get(sport, sport.upper())


def ingest_fit_file(
    file_path: str,
    garmin_activity_id: int,
    user_id: str,
    device_id: int,
    activity_name: str = "Atividade Garmin",
) -> dict:
    """Importa um .FIT. Retorna resumo do que foi feito.

    O tipo de esporte, distancia e duracao saem da propria sessao do .FIT.
    Se garmin_activity_id ja existir, retorna status 'skipped' sem regravar.
    """
    con = get_connection()

    # 1) Ja importamos essa atividade antes? (idempotencia)
    existing = con.execute(
        "SELECT activity_id FROM dim_activities WHERE garmin_activity_id = ?",
        [garmin_activity_id],
    ).fetchone()
    if existing is not None:
        return {"status": "skipped", "activity_id": str(existing[0]), "records": 0}

    # 2) Parseia o arquivo.
    parser = FitParser(file_path)
    if not parser.validate_file():
        raise ValueError(f"Arquivo .FIT invalido: {file_path}")
    df = parser.to_dataframe()
    if df.is_empty():
        raise ValueError("Nenhum record encontrado no .FIT")

    # 3) Cria a linha da atividade usando os metadados da sessao (tipo, distancia,
    #    duracao). Se faltar start_time na sessao, cai pro 1o timestamp da serie.
    meta = parser.session_metadata()
    primary_type = _derive_primary_type(meta.get("sport"), meta.get("sub_sport"))
    start_time = meta.get("start_time") or df["timestamp"].min()

    activity_id = str(uuid.uuid4())
    con.execute(
        """INSERT INTO dim_activities
           (activity_id, garmin_activity_id, activity_name, start_time,
            total_distance_meters, total_duration_seconds, primary_type,
            hr_zone_boundaries, hr_zone_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            activity_id, garmin_activity_id, activity_name, start_time,
            meta.get("total_distance_meters"), meta.get("total_duration_seconds"),
            primary_type,
            meta.get("hr_zone_boundaries"), meta.get("hr_zone_seconds"),
        ],
    )

    # 4) Insere a telemetria. telemetry_id continua a partir do maior ja existente.
    next_id = (con.execute("SELECT COALESCE(MAX(telemetry_id), -1) FROM fact_telemetry").fetchone()[0]) + 1
    for i, row in enumerate(df.to_dicts()):
        con.execute(
            """INSERT INTO fact_telemetry
               (telemetry_id, activity_id, user_id, device_id, timestamp,
                heart_rate, cadence, latitude, longitude, altitude,
                vertical_oscillation, stance_time_ms, speed_ms, distance_m)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                next_id + i, activity_id, user_id, device_id, row["timestamp"],
                row["heart_rate"], row["cadence"], row["latitude"], row["longitude"],
                row["altitude"], row["vertical_oscillation"], row["stance_time_ms"],
                row["speed_ms"], row["distance_m"],
            ],
        )

    return {
        "status": "imported",
        "activity_id": activity_id,
        "primary_type": primary_type,
        "records": df.height,
    }
