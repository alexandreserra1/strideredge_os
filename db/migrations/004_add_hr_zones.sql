-- 004_add_hr_zones.sql — guarda as zonas de FC que o PROPRIO Garmin calculou.
-- O .FIT traz, no resumo da sessao: os limites das zonas (hr_zone_high_boundary,
-- o ultimo = FC maxima real do atleta) e o tempo em cada zona (time_in_hr_zone).
--
-- Guardamos como ARRAYS na dim_activities (1 linha por treino) — sem tabela
-- extra e sem join, fiel a configuracao real do relogio em vez de estimar.
-- Migracao aditiva e idempotente.

ALTER TABLE dim_activities ADD COLUMN IF NOT EXISTS hr_zone_boundaries INTEGER[];
ALTER TABLE dim_activities ADD COLUMN IF NOT EXISTS hr_zone_seconds    FLOAT[];
