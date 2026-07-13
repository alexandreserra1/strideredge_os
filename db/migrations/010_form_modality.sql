-- Modalidade da análise de vídeo. Hoje só 'run' (o motor é de corrida); o campo já existe
-- pra quando entrarem Hyrox/CrossFit — sem re-migrar depois. DuckDB roda IF NOT EXISTS.
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS modality VARCHAR DEFAULT 'run';
