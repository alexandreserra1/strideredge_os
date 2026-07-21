-- 018: planos corretivos gerados (EPIC C). Um plano por geração, ligado ao atleta e à análise
-- que o originou. `plan` = JSON do build_plan (semanas/sessões/fontes). Persistido só p/ logado;
-- re-gerar por novo vídeo cria outro (histórico de planos = progressão do atleta ao longo do tempo).
CREATE TABLE IF NOT EXISTS training_plans (
    id           UUID PRIMARY KEY,
    user_id      TEXT NOT NULL,
    analysis_id  UUID,
    weeks        INTEGER,
    plan         TEXT,               -- JSON do plano corretivo
    created_at   TIMESTAMP DEFAULT now()
);
