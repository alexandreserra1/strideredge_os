-- 021: capability de convidado é temporária; conta autenticada mantém a própria análise.
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS access_token_expires_at TIMESTAMP;
