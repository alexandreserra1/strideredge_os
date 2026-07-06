"""Testes de autenticação — hasher, token, cadastro único, login e Google (fake).

Rodam no banco temporário do conftest (migração 006 cria auth_users).
"""

import pytest
from fastapi.testclient import TestClient

from api.auth import AuthError, AuthService, PasswordHasher, TokenSigner
from api.main import app

client = TestClient(app)


# ---------- unidades ----------

def test_hasher_nunca_guarda_senha_em_claro():
    h = PasswordHasher()
    stored = h.hash("supersegura123")
    assert "supersegura123" not in stored and stored.startswith("pbkdf2$")
    assert h.verify("supersegura123", stored)
    assert not h.verify("errada", stored)
    assert not h.verify("qualquer", None)          # conta só-Google não tem senha


def test_hash_com_salt_diferente_a_cada_vez():
    h = PasswordHasher()
    assert h.hash("mesma") != h.hash("mesma")      # salt aleatório


def test_token_assina_e_expira():
    s = TokenSigner(secret=b"x" * 32, ttl_s=60)
    tok = s.sign({"sub": "abc"})
    assert s.verify(tok)["sub"] == "abc"
    assert s.verify(tok + "corrompido") is None
    expirado = TokenSigner(secret=b"x" * 32, ttl_s=-1).sign({"sub": "abc"})
    assert TokenSigner(secret=b"x" * 32).verify(expirado) is None


# ---------- serviço / API ----------

def test_cadastro_login_e_me():
    r = client.post("/api/v1/auth/register", json={
        "name": "Alexandre", "email": "Alex@Teste.com", "password": "corrida12345"})
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "alex@teste.com"   # normalizado
    # login com a senha certa
    r2 = client.post("/api/v1/auth/login", json={"email": "alex@teste.com", "password": "corrida12345"})
    assert r2.status_code == 200 and r2.json()["token"]
    # /me com o token
    r3 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r2.json()['token']}"})
    assert r3.status_code == 200 and r3.json()["name"] == "Alexandre"


def test_email_duplicado_409():
    payload = {"name": "A", "email": "dup@teste.com", "password": "corrida12345"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_senha_errada_401_sem_vazar_existencia():
    client.post("/api/v1/auth/register", json={
        "name": "B", "email": "b@teste.com", "password": "corrida12345"})
    r1 = client.post("/api/v1/auth/login", json={"email": "b@teste.com", "password": "errada123"})
    r2 = client.post("/api/v1/auth/login", json={"email": "nao-existe@teste.com", "password": "errada123"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]   # mesma mensagem: não revela e-mail


def test_validacoes_422():
    assert client.post("/api/v1/auth/register", json={
        "name": "C", "email": "invalido", "password": "corrida12345"}).status_code == 422
    assert client.post("/api/v1/auth/register", json={
        "name": "C", "email": "c@teste.com", "password": "curta"}).status_code == 422


def test_google_cria_e_vincula(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-teste")
    svc = AuthService()
    monkeypatch.setattr(svc, "_google_tokeninfo", lambda cred: {
        "aud": "client-teste", "email_verified": "true",
        "email": "g@teste.com", "sub": "google-123", "name": "G Runner"})
    out = svc.login_google("fake-credential")
    assert out["user"]["email"] == "g@teste.com" and out["token"]
    # repetir NÃO duplica (mesmo e-mail -> mesma conta)
    again = svc.login_google("fake-credential")
    assert again["user"]["user_id"] == out["user"]["user_id"]


def test_google_sem_config_503(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    with pytest.raises(AuthError) as e:
        AuthService().login_google("x")
    assert e.value.status == 503


def test_google_aud_errado_401(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-teste")
    svc = AuthService()
    monkeypatch.setattr(svc, "_google_tokeninfo", lambda cred: {
        "aud": "OUTRO-client", "email_verified": "true",
        "email": "x@teste.com", "sub": "s"})
    with pytest.raises(AuthError) as e:
        svc.login_google("x")
    assert e.value.status == 401
