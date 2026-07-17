-- 015: liga a análise de forma ao usuário. Necessário pra CORRELACIONAR o histórico de vídeos de
-- um atleta com a lesão que ele reportou (a ponte de ML). NULL = análise anônima (convidado) —
-- não entra na correlação. Preenchido pelo form_upload a partir do token, quando logado.
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS user_id TEXT;
