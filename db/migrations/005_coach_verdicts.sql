-- 005: cache de vereditos do coach.
-- Idempotência do POST /coach (repetir não paga outros ~30s de LLM) e review
-- instantânea ao reabrir o treino. structured = JSON do veredito estruturado.
CREATE TABLE IF NOT EXISTS cache_coach_verdicts (
    activity_id UUID PRIMARY KEY,
    verdict     TEXT NOT NULL,
    structured  TEXT NOT NULL,
    model       TEXT,
    created_at  TIMESTAMP DEFAULT current_timestamp
);
