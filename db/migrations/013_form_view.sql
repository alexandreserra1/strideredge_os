-- 013: vista da câmera na análise de forma. 'lateral' (sagital: cadência, pisada, contato/voo)
-- ou 'frontal' (plano frontal: queda pélvica, valgo de joelho). O motor Rust roda o conjunto
-- de métricas certo por vista. Default 'lateral' (o que já existia).
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS view VARCHAR DEFAULT 'lateral';
