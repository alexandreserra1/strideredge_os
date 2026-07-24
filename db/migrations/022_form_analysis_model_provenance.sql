-- 022: snapshot de proveniência do motor que gerou cada análise.
-- Não persistimos paths locais: só a seleção do servidor, versão e hashes dos assets. Isso permite
-- comparar YOLO/Halpe depois e reproduzir uma saída sem expor a topologia do host ao cliente.
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS backend_requested VARCHAR;
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS backend_effective VARCHAR;
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS model_version VARCHAR;
ALTER TABLE form_analyses ADD COLUMN IF NOT EXISTS model_assets TEXT;
