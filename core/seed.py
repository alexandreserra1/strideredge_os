"""core/seed.py — popula o banco com UMA atividade fake (dados de exemplo).

Fatia 0: serve so para ter dados reais no DuckDB sem depender da Garmin.
Roda as migracoes, insere usuario/device/atividade fixos e carrega o CSV.
"""

import polars as pl

from core.database import get_connection, run_migrations, PROJECT_ROOT

# IDs fixos para a atividade fake — assim a API sempre sabe o que consultar.
SEED_USER_ID = "11111111-1111-1111-1111-111111111111"
SEED_DEVICE_ID = 1
SEED_ACTIVITY_ID = "22222222-2222-2222-2222-222222222222"

SEED_CSV = PROJECT_ROOT / "storage" / "seed_activity.csv"


def seed() -> str:
    """Cria o schema e insere a atividade de exemplo. Idempotente."""
    con = get_connection()
    run_migrations(con)

    # Le o CSV num DataFrame Polars (rapido e tipado).
    df = pl.read_csv(SEED_CSV)

    # INSERT OR IGNORE: se ja existir (mesma PK / UNIQUE), nao duplica.
    con.execute(
        "INSERT OR IGNORE INTO dim_users (user_id, name) VALUES (?, ?)",
        [SEED_USER_ID, "Atleta Demo"],
    )
    con.execute(
        "INSERT OR IGNORE INTO dim_devices (device_id, manufacturer, model_name) VALUES (?, ?, ?)",
        [SEED_DEVICE_ID, "Garmin", "Forerunner 165"],
    )
    con.execute(
        """INSERT OR IGNORE INTO dim_activities
           (activity_id, garmin_activity_id, activity_name, start_time, primary_type)
           VALUES (?, ?, ?, ?, ?)""",
        [SEED_ACTIVITY_ID, 9001, "Corrida Demo", "2026-06-12 07:00:00", "RUN"],
    )

    # Insere a telemetria linha a linha. enumerate() gera o telemetry_id (PK).
    rows = df.to_dicts()  # lista de dicionarios, um por linha do CSV
    for i, row in enumerate(rows):
        con.execute(
            """INSERT OR IGNORE INTO fact_telemetry
               (telemetry_id, activity_id, user_id, device_id, timestamp,
                heart_rate, cadence, latitude, longitude, altitude)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                i, SEED_ACTIVITY_ID, SEED_USER_ID, SEED_DEVICE_ID, row["timestamp"],
                row["heart_rate"], row["cadence"], row["latitude"],
                row["longitude"], row["altitude"],
            ],
        )

    return SEED_ACTIVITY_ID


if __name__ == "__main__":
    activity_id = seed()
    print(f"Seed concluido. activity_id = {activity_id}")
