-- 019: autorização de análise anônima. Usuário autenticado acessa pelo user_id;
-- convidado recebe uma capability aleatória e só o hash fica persistido.
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS access_token_hash VARCHAR;
