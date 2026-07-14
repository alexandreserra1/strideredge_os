"""api/auth.py — autenticação: cadastro, login, vínculo Google e sessão.

Desenho OOP (composição, como o resto do projeto):
  - PasswordHasher : PBKDF2-HMAC-SHA256 + salt (stdlib) — senha NUNCA em claro no banco.
  - TokenSigner    : token de sessão assinado (HMAC-SHA256) com expiração —
                     stateless, sem dependência de lib de JWT.
  - AuthService    : COMPOE os dois + a conexão única do DuckDB. Regras de
                     negócio: e-mail único, senha mínima, upsert do Google.

Sem overengineering (constituição §2): stdlib resolve hash e token; OAuth do
Google entra pela validação do ID token na API deles (zero SDK).
"""

import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from typing import Optional

import httpx

from core.database import get_connection, PROJECT_ROOT

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SECRET_PATH = PROJECT_ROOT / "storage" / ".auth_secret"


class AuthError(Exception):
    """Erro de autenticação com status HTTP sugerido (a API traduz)."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class PasswordHasher:
    """PBKDF2-HMAC-SHA256 (stdlib) com salt aleatório por senha + comparação em
    tempo constante. 600k iterações = recomendação OWASP p/ PBKDF2-SHA256."""

    ITERATIONS = 600_000

    def hash(self, password: str) -> str:
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, self.ITERATIONS)
        return (f"pbkdf2${self.ITERATIONS}$"
                f"{base64.b64encode(salt).decode()}${base64.b64encode(key).decode()}")

    def verify(self, password: str, stored: Optional[str]) -> bool:
        if not stored:
            return False
        try:
            _, iters, s64, k64 = stored.split("$")
            salt, expected = base64.b64decode(s64), base64.b64decode(k64)
            key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
            return hmac.compare_digest(key, expected)
        except Exception:
            return False


class TokenSigner:
    """Token de sessão: payload JSON assinado com HMAC-SHA256 + expiração.

    O segredo vive em storage/.auth_secret (gerado na 1ª vez, fora do git) —
    tokens sobrevivem a restart sem env var manual.
    """

    def __init__(self, secret: Optional[bytes] = None, ttl_s: int = 7 * 24 * 3600):
        self.secret = secret or self._load_secret()
        self.ttl_s = ttl_s

    @staticmethod
    def _load_secret() -> bytes:
        if _SECRET_PATH.exists():
            return _SECRET_PATH.read_bytes()
        secret = os.urandom(32)
        _SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SECRET_PATH.write_bytes(secret)
        return secret

    def sign(self, payload: dict) -> str:
        body = base64.urlsafe_b64encode(
            json.dumps({**payload, "exp": int(time.time()) + self.ttl_s}).encode())
        sig = hmac.new(self.secret, body, hashlib.sha256).digest()
        return f"{body.decode()}.{base64.urlsafe_b64encode(sig).decode()}"

    def verify(self, token: str) -> Optional[dict]:
        """Payload do token se a assinatura e a validade batem; senão None."""
        try:
            body64, sig64 = token.split(".")
            # compara a assinatura CODIFICADA (match exato): b64decode ignora lixo
            # após o padding '=', o que deixaria passar token com sufixo adulterado
            expected = base64.urlsafe_b64encode(
                hmac.new(self.secret, body64.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(expected, sig64.encode()):
                return None
            payload = json.loads(base64.urlsafe_b64decode(body64))
            return payload if payload.get("exp", 0) > time.time() else None
        except Exception:
            return None


class AuthService:
    """Regras de conta: cadastro único por e-mail, login e vínculo Google."""

    GOOGLE_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"

    def __init__(self, hasher: PasswordHasher = None, signer: TokenSigner = None):
        self.hasher = hasher or PasswordHasher()
        self.signer = signer or TokenSigner()

    # ---------- helpers ----------

    @staticmethod
    def _normalize_email(email: str) -> str:
        email = (email or "").strip().lower()
        if not _EMAIL_RE.match(email):
            raise AuthError(422, "E-mail inválido")
        return email

    def _issue(self, user_id: str, name: str, email: str) -> dict:
        token = self.signer.sign({"sub": user_id, "email": email})
        return {"token": token, "user": {"user_id": user_id, "name": name, "email": email}}

    # ---------- casos de uso ----------

    def register(self, name: str, email: str, password: str) -> dict:
        email = self._normalize_email(email)
        if len(password or "") < 8:
            raise AuthError(422, "Senha precisa de pelo menos 8 caracteres")
        if not (name or "").strip():
            raise AuthError(422, "Nome é obrigatório")
        con = get_connection()
        if con.execute("SELECT 1 FROM auth_users WHERE email = ?", [email]).fetchone():
            raise AuthError(409, "Este e-mail já tem cadastro")
        user_id = str(uuid.uuid4())
        con.execute(
            "INSERT INTO auth_users (user_id, name, email, password_hash) VALUES (?, ?, ?, ?)",
            [user_id, name.strip(), email, self.hasher.hash(password)])
        return self._issue(user_id, name.strip(), email)

    def login(self, email: str, password: str) -> dict:
        email = self._normalize_email(email)
        row = get_connection().execute(
            "SELECT user_id, name, password_hash FROM auth_users WHERE email = ?",
            [email]).fetchone()
        # verify roda mesmo sem usuário (timing uniforme; não revela se o e-mail existe)
        ok = self.hasher.verify(password, row[2] if row else None)
        if not row or not ok:
            raise AuthError(401, "E-mail ou senha incorretos")
        return self._issue(str(row[0]), row[1], email)

    def login_google(self, credential: str) -> dict:
        """Valida o ID token na API do Google e cria/vincula a conta pelo e-mail."""
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        if not client_id:
            raise AuthError(503, "Login com Google não configurado (defina GOOGLE_CLIENT_ID)")
        info = self._google_tokeninfo(credential)
        if info.get("aud") != client_id or info.get("email_verified") not in ("true", True):
            raise AuthError(401, "Token do Google inválido")
        email = self._normalize_email(info["email"])
        sub, name = info["sub"], info.get("name") or email.split("@")[0]
        con = get_connection()
        row = con.execute("SELECT user_id, name FROM auth_users WHERE email = ?", [email]).fetchone()
        if row:                                       # conta existente -> garante o vínculo
            con.execute("UPDATE auth_users SET google_sub = ? WHERE user_id = ?", [sub, str(row[0])])
            return self._issue(str(row[0]), row[1], email)
        user_id = str(uuid.uuid4())
        con.execute(
            "INSERT INTO auth_users (user_id, name, email, google_sub) VALUES (?, ?, ?, ?)",
            [user_id, name, email, sub])
        return self._issue(user_id, name, email)

    def _google_tokeninfo(self, credential: str) -> dict:
        """Chamada real ao Google (separada p/ os testes trocarem por fake)."""
        r = httpx.get(self.GOOGLE_TOKENINFO, params={"id_token": credential}, timeout=10.0)
        if r.status_code != 200:
            raise AuthError(401, "Token do Google inválido")
        return r.json()

    def login_strava(self, code: str, client) -> dict:
        """Login/cadastro via Strava (OAuth). Troca o `code` por token+atleta, cria/vincula a
        conta pelo strava_athlete_id (o Strava NÃO retorna email → placeholder), guarda os
        tokens e devolve a sessão nossa. NÃO importa histórico — isso é job de fila (o
        controller enfileira). `client` = StravaClient (injetável → testável com fake)."""
        data = client.exchange_code(code)
        athlete = data["athlete"]
        athlete_id = athlete["id"]
        con = get_connection()
        row = con.execute(
            "SELECT user_id, name, email FROM auth_users WHERE strava_athlete_id = ?",
            [athlete_id]).fetchone()
        if row:
            user_id, name, email = str(row[0]), row[1], row[2]
        else:
            user_id = str(uuid.uuid4())
            nome = " ".join(x for x in (athlete.get("firstname"), athlete.get("lastname")) if x)
            name = nome.strip() or f"Atleta {athlete_id}"
            email = f"strava_{athlete_id}@strava.local"   # placeholder (Strava não dá email)
            con.execute(
                "INSERT INTO auth_users (user_id, name, email, strava_athlete_id) "
                "VALUES (?, ?, ?, ?)", [user_id, name, email, athlete_id])
        # upsert dos tokens (rotacionam; expires_at vem em epoch segundos)
        con.execute("DELETE FROM strava_tokens WHERE user_id = ?", [user_id])
        con.execute(
            "INSERT INTO strava_tokens (user_id, athlete_id, access_token, refresh_token, expires_at) "
            "VALUES (?, ?, ?, ?, to_timestamp(?))",
            [user_id, athlete_id, data["access_token"], data["refresh_token"], data["expires_at"]])
        return self._issue(user_id, name, email)

    def me(self, token: str) -> dict:
        payload = self.signer.verify(token or "")
        if not payload:
            raise AuthError(401, "Sessão inválida ou expirada")
        row = get_connection().execute(
            "SELECT user_id, name, email FROM auth_users WHERE user_id = ?",
            [payload["sub"]]).fetchone()
        if not row:
            raise AuthError(401, "Conta não existe mais")
        return {"user_id": str(row[0]), "name": row[1], "email": row[2]}
