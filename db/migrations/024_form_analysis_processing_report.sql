-- 024: telemetria interna de duração por estágio da análise.
-- Não contém vídeo, path local, token, identidade ou métrica biométrica; não é exposta na API.
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS processing_report TEXT;
