-- 006: contas de usuário (login/cadastro).
-- Senha NUNCA em claro: password_hash = PBKDF2+salt (ver api/auth.py).
-- email UNIQUE = cadastro único; google_sub = vínculo com conta Google (opcional).
CREATE TABLE IF NOT EXISTS auth_users (
    user_id       UUID PRIMARY KEY,
    name          VARCHAR NOT NULL,
    email         VARCHAR NOT NULL UNIQUE,
    password_hash VARCHAR,              -- NULL quando a conta é só-Google
    google_sub    VARCHAR UNIQUE,       -- id estável do Google (NULL sem vínculo)
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
