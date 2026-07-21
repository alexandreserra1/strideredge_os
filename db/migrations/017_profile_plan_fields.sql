-- 017: campos de perfil pro PLANO CORRETIVO e a RECOMENDAÇÃO DE TÊNIS (EPIC B/C/D).
-- Todos opcionais (degrada gracioso). goal_timeframe_weeks = "em quanto tempo quero melhorar";
-- weekly_volume_km + days_per_week = base pra progressão ~10%/semana; current_shoe + footstrike_pref
-- alimentam a recomendação de tênis (pisada↔amortecimento).
ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS goal_timeframe_weeks INTEGER;
ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS weekly_volume_km DOUBLE;
ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS days_per_week INTEGER;
ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS current_shoe TEXT;
ALTER TABLE athlete_profile ADD COLUMN IF NOT EXISTS footstrike_pref TEXT;
