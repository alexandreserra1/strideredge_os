-- 008: análises de forma (vídeo -> métricas biomecânicas via stride-vision).
-- O VÍDEO NUNCA entra no banco: fica em storage/videos/{id}/ (filesystem);
-- aqui só caminho + métricas (JSON) — as métricas são o que vale guardar.
CREATE TABLE IF NOT EXISTS form_analyses (
    analysis_id UUID PRIMARY KEY,
    activity_id UUID,                  -- treino vinculado (opcional -> comparação c/ Garmin)
    status      VARCHAR NOT NULL,      -- processing | done | failed
    video_path  VARCHAR,               -- overlay.mp4 (re-encodado, com esqueleto)
    metrics     TEXT,                  -- JSON do stride-vision
    error       VARCHAR,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
