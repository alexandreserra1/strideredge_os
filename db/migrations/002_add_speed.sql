-- 002_add_speed.sql — adiciona velocidade instantanea a fact_telemetry.
-- Migracao ADITIVA: ADD COLUMN IF NOT EXISTS nao destroi dados existentes e
-- pode rodar varias vezes. Necessaria para a eficiencia metabolica (§6.2).
-- Unidade: metros por segundo (validado: enhanced_avg_speed == distancia/tempo).

ALTER TABLE fact_telemetry ADD COLUMN IF NOT EXISTS speed_ms FLOAT;
