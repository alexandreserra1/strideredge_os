-- 023: observabilidade interna de comparações shadow (BlazePose principal × YOLO temporário).
-- O relatório não contém vídeo, path local nem substitui `metrics`; serve apenas para medir
-- qualidade/desempenho antes de qualquer promoção do backend experimental.
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS shadow_report TEXT;
