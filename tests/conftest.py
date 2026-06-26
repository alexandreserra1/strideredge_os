"""Configuração dos testes — banco TEMPORÁRIO semeado (hermético).

Em vez de depender do strideredge.db local (construído de .FIT pessoais), cada
sessão de teste cria um DuckDB temporário e o semeia com dados sintéticos. Assim
a suíte é reproduzível em qualquer máquina / no CI.
"""

import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

USER_ID = "11111111-1111-1111-1111-111111111111"
FLORIPA_ID = "22222222-2222-2222-2222-222222222222"
OTHER_ID = "33333333-3333-3333-3333-333333333333"


def _seed_run(con, counter, activity_id, garmin_id, name, with_gps, cad_base, hr_base, n=120):
    """Insere uma atividade RUN + n leituras de telemetria sintéticas."""
    start = datetime(2026, 6, 11, 7, 0, 0)
    # zonas de FC (só pra Floripa, para o HrZoneAnalyzer ter dado)
    boundaries = [97, 117, 139, 158, 178, 198] if with_gps else None
    seconds = [10.0, 20.0, 30.0, 40.0, 20.0, 0.0, 0.0] if with_gps else None
    con.execute(
        """INSERT INTO dim_activities
           (activity_id, garmin_activity_id, activity_name, start_time,
            total_distance_meters, total_duration_seconds, primary_type,
            hr_zone_boundaries, hr_zone_seconds)
           VALUES (?, ?, ?, ?, ?, ?, 'RUN', ?, ?)""",
        [activity_id, garmin_id, name, start, n * 3.0, float(n), boundaries, seconds],
    )
    for i in range(n):
        # cadência cai ~10% no último terço (gera ponto de quebra); FC sobe
        cad = cad_base if i < 2 * n // 3 else round(cad_base * 0.88)
        hr = hr_base + (12 if i >= 2 * n // 3 else round(i / n * 6))
        lat = -27.60 - i * 1e-5 if with_gps else None
        lon = -48.57 + i * 1e-5 if with_gps else None
        alt = 700 + 8 * math.sin(i / 15) if with_gps else None
        con.execute(
            """INSERT INTO fact_telemetry
               (telemetry_id, activity_id, user_id, device_id, timestamp,
                heart_rate, cadence, latitude, longitude, altitude,
                vertical_oscillation, stance_time_ms, speed_ms, distance_m)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)""",
            [counter[0], activity_id, USER_ID, start + timedelta(seconds=i),
             hr, cad, lat, lon, alt, 3.0, float(i * 3)],
        )
        counter[0] += 1


@pytest.fixture(scope="session", autouse=True)
def _temp_db(tmp_path_factory):
    from core.database import close_connection, get_connection, run_migrations

    db_path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["STRIDEREDGE_DB"] = str(db_path)
    close_connection()  # descarta qualquer conexão ao banco real

    con = get_connection()
    run_migrations(con)
    con.execute("INSERT INTO dim_users (user_id, name) VALUES (?, 'Atleta Teste')", [USER_ID])
    con.execute("INSERT INTO dim_devices (device_id, manufacturer, model_name) VALUES (1, 'Garmin', 'Test')")
    counter = [0]
    _seed_run(con, counter, FLORIPA_ID, 1, "Corrida Floripa", with_gps=True, cad_base=165, hr_base=150)
    _seed_run(con, counter, OTHER_ID, 2, "Corrida B", with_gps=False, cad_base=170, hr_base=140)

    from analytics.training_load import refresh_summary_cache
    refresh_summary_cache()

    yield
    close_connection()
    os.environ.pop("STRIDEREDGE_DB", None)
