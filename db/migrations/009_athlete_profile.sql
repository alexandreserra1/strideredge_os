-- Perfil do atleta: contexto pessoal p/ personalizar os alvos biomecânicos.
-- Opcional (degrada gracioso): sem perfil, o motor usa defaults + proporções da pose.
CREATE TABLE IF NOT EXISTS athlete_profile (
    user_id       TEXT PRIMARY KEY,
    height_cm     DOUBLE,
    weight_kg     DOUBLE,
    years_running DOUBLE,
    goal          TEXT,
    updated_at    TIMESTAMP DEFAULT now()
);
