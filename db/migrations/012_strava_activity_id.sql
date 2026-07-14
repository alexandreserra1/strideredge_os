-- 012: idempotência do import Strava. Espelha garmin_activity_id UNIQUE (constituição §8):
-- reimportar o histórico não duplica atividade. Índice único à parte (ALTER não faz UNIQUE
-- inline); permite múltiplos NULL (atividades vindas do .FIT/Garmin, sem id do Strava).
ALTER TABLE dim_activities ADD COLUMN IF NOT EXISTS strava_activity_id BIGINT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_strava_activity ON dim_activities(strava_activity_id);
