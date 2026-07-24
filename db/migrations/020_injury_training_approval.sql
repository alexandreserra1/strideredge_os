-- 020: relato do atleta é dado clínico útil, mas não vira outcome global automaticamente.
-- Somente uma operação administrativa explícita pode aprovar um caso para treinar Bayes/RF.
ALTER TABLE injury_reports ADD COLUMN IF NOT EXISTS training_approved BOOLEAN DEFAULT FALSE;
