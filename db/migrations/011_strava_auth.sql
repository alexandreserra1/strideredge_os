-- 011: login + import via Strava (OAuth oficial, sem senha).
-- O Strava OAuth NÃO retorna email, então a conta é chaveada pelo strava_athlete_id.
-- O email vira um placeholder (strava_{id}@strava.local), atualizável depois — assim
-- mantemos o email NOT NULL/UNIQUE original sem precisar de DROP NOT NULL (que o DuckDB
-- não faz depois de existir índice). Índice único à parte (ADD COLUMN ... UNIQUE inline
-- não é suportado via ALTER); permite múltiplos NULL (contas sem vínculo Strava).
ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS strava_athlete_id BIGINT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_strava_athlete ON auth_users(strava_athlete_id);

-- Tokens do Strava (rotacionam/expiram — refresh quando vence). SENSÍVEL: nunca logar.
CREATE TABLE IF NOT EXISTS strava_tokens (
    user_id       UUID PRIMARY KEY,
    athlete_id    BIGINT,
    access_token  VARCHAR NOT NULL,
    refresh_token VARCHAR NOT NULL,
    expires_at    TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
