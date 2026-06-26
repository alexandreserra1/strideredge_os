-- 003_add_distance.sql — adiciona distancia acumulada a fact_telemetry.
-- O .FIT grava 'distance' (metros acumulados) em cada leitura. Guardar o valor
-- real e mais exato que derivar de velocidade x tempo, e destrava splits/pace/grade.
-- Migracao aditiva e idempotente.

ALTER TABLE fact_telemetry ADD COLUMN IF NOT EXISTS distance_m FLOAT;
