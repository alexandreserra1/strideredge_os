-- 014: log de lesão do atleta (auto-relato ESTRUTURADO, base do dataset de risco).
-- Uma linha por lesão reportada (nível atleta, longitudinal — não ligada a UM vídeo). As 4
-- perguntas OSTRC (participação/volume/desempenho/dor, 0–3) permitem calcular a severidade
-- 0–100 (padrão OSTRC-BR) na leitura. region/diagnosis = vocabulário controlado (injury_taxonomy).
CREATE TABLE IF NOT EXISTS injury_reports (
    id             UUID PRIMARY KEY,
    user_id        TEXT NOT NULL,
    region         TEXT,
    diagnosis      TEXT,
    side           TEXT,               -- esquerdo | direito | ambos
    onset_date     DATE,               -- quando começou (pra correlacionar com análises anteriores)
    q_participation INT,               -- OSTRC Q1: reduziu/parou treino? (0–3)
    q_volume        INT,               -- OSTRC Q2: reduziu volume? (0–3)
    q_performance   INT,               -- OSTRC Q3: afetou desempenho? (0–3)
    q_pain          INT,               -- OSTRC Q4: dor? (0–3)
    notes          TEXT,
    reported_at    TIMESTAMP DEFAULT now()
);
