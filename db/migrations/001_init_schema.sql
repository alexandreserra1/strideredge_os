-- 001_init_schema.sql — Inicializacao do Star Schema analitico (DuckDB).
-- Star Schema = tabelas de DIMENSAO (contexto) ao redor de uma tabela de FATO
-- (a serie temporal granular, segundo a segundo).

-- Usa IF NOT EXISTS em tudo para a migracao poder rodar varias vezes sem quebrar.

CREATE TABLE IF NOT EXISTS dim_users (
    user_id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    birth_date DATE,
    weight_kg FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_devices (
    device_id INTEGER PRIMARY KEY,
    manufacturer VARCHAR,
    model_name VARCHAR,
    firmware_version VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_activities (
    activity_id UUID PRIMARY KEY,
    -- AJUSTE (idempotencia): id original da Garmin. UNIQUE impede que o cronjob
    -- importe a mesma atividade duas vezes e duplique a telemetria.
    garmin_activity_id BIGINT UNIQUE,
    activity_name VARCHAR,
    start_time TIMESTAMP NOT NULL,
    total_distance_meters FLOAT,
    total_duration_seconds FLOAT,
    primary_type VARCHAR -- 'RUN', 'HYROX_WOD', 'FUTEVOLEI'
);

CREATE TABLE IF NOT EXISTS fact_telemetry (
    telemetry_id BIGINT PRIMARY KEY,
    activity_id UUID NOT NULL,
    user_id UUID NOT NULL,
    device_id INTEGER,
    timestamp TIMESTAMP NOT NULL,
    heart_rate SMALLINT,
    cadence SMALLINT,
    latitude DOUBLE,
    longitude DOUBLE,
    altitude FLOAT,
    -- AJUSTE (nullability): metricas avancadas de dinamica de corrida. Uma fita
    -- peitoral simples nao fornece estes campos, entao podem ser NULL.
    vertical_oscillation FLOAT,
    stance_time_ms FLOAT,
    FOREIGN KEY (activity_id) REFERENCES dim_activities(activity_id),
    FOREIGN KEY (user_id) REFERENCES dim_users(user_id),
    FOREIGN KEY (device_id) REFERENCES dim_devices(device_id)
);

-- Cache de agregados materializados para o dashboard (evita recomputar tudo).
CREATE TABLE IF NOT EXISTS cache_workout_summary (
    activity_id UUID PRIMARY KEY,
    avg_hr FLOAT,
    max_hr FLOAT,
    avg_cadence FLOAT,
    total_elevation_gain FLOAT,
    metabolic_efficiency_score FLOAT,
    breaking_point_timestamp TIMESTAMP
);
