-- 007: séries de força do Garmin (só existem em treinos gravados no modo Força).
-- Fonte: set_mesgs do .FIT — exercício (categoria), reps, peso, duração por série.
CREATE TABLE IF NOT EXISTS fact_strength_sets (
    activity_id UUID NOT NULL,
    set_index   INTEGER NOT NULL,
    exercise    VARCHAR,             -- categoria Garmin (ex: bench_press)
    reps        INTEGER,
    weight_kg   FLOAT,
    duration_s  FLOAT,
    start_time  TIMESTAMP,
    PRIMARY KEY (activity_id, set_index)
);
