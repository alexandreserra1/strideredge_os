"""Login + import via Strava, com StravaClient FAKE (sem rede). Usa o DuckDB de teste."""

import time
from uuid import uuid4

from fastapi.testclient import TestClient

from api.auth import AuthService
from api.deps import get_auth_service, get_job_queue, get_strava_client, get_strava_importer
from api.main import app
from core.database import get_connection
from core.jobs import JobQueue
from ingestion.strava_importer import StravaImporter, _primary_type


class _FakeStravaClient:
    """Cliente Strava falso: devolve atleta/atividades fixos, registra refresh."""

    def __init__(self, athlete_id=555, activities=None, expires_in=3600):
        self.athlete_id = athlete_id
        self.activities = activities or []
        self.expires_in = expires_in
        self.refreshed = False

    def authorize_url(self, redirect_uri, state=""):
        return "https://www.strava.com/oauth/authorize?fake=1"

    def exchange_code(self, code):
        return {"access_token": "acc", "refresh_token": "ref",
                "expires_at": int(time.time()) + self.expires_in,
                "athlete": {"id": self.athlete_id, "firstname": "Alex", "lastname": "Serra"}}

    def refresh(self, refresh_token):
        self.refreshed = True
        return {"access_token": "acc2", "refresh_token": "ref2",
                "expires_at": int(time.time()) + 3600}

    def get_activities(self, access_token, page=1, per_page=100):
        return self.activities if page == 1 else []


def test_primary_type_mapeia_esporte():
    assert _primary_type("Run") == "RUN"
    assert _primary_type("WeightTraining") == "STRENGTH"
    assert _primary_type("Workout") == "HIIT"
    assert _primary_type("Coisa") == "OTHER"


def test_login_strava_cria_conta_por_athlete_id_sem_email():
    con = get_connection()
    client = _FakeStravaClient(athlete_id=5551)
    auth = AuthService()
    try:
        s1 = auth.login_strava("code", client)
        assert s1["user"]["email"] == "strava_5551@strava.local"   # placeholder (Strava não dá email)
        uid = s1["user"]["user_id"]
        assert con.execute("SELECT 1 FROM strava_tokens WHERE user_id=?", [uid]).fetchone()
        # relogin do mesmo atleta NÃO duplica
        s2 = auth.login_strava("code2", client)
        assert s2["user"]["user_id"] == uid
        assert con.execute("SELECT COUNT(*) FROM auth_users WHERE strava_athlete_id=5551").fetchone()[0] == 1
    finally:
        con.execute("DELETE FROM strava_tokens WHERE athlete_id=5551")
        con.execute("DELETE FROM auth_users WHERE strava_athlete_id=5551")


def _seed_token(con, uid, expires_in=3600):
    con.execute(
        "INSERT INTO strava_tokens (user_id, athlete_id, access_token, refresh_token, expires_at) "
        "VALUES (?, 1, 'acc', 'ref', to_timestamp(?))", [uid, int(time.time()) + expires_in])


def test_import_history_mapeia_e_e_idempotente():
    con = get_connection()
    uid = str(uuid4())
    _seed_token(con, uid)
    acts = [
        {"id": 7001, "name": "Corrida", "sport_type": "Run", "distance": 5000.0,
         "elapsed_time": 1500, "start_date": "2026-07-01T07:00:00Z"},
        {"id": 7002, "name": "Força", "sport_type": "WeightTraining", "distance": 0.0,
         "elapsed_time": 3000, "start_date": "2026-07-02T07:00:00Z"},
    ]
    imp = StravaImporter(_FakeStravaClient(activities=acts))
    try:
        r1 = imp.import_history(uid)
        assert r1["imported"] == 2
        tipos = {row[0]: row[1] for row in con.execute(
            "SELECT strava_activity_id, primary_type FROM dim_activities "
            "WHERE strava_activity_id IN (7001, 7002)").fetchall()}
        assert tipos[7001] == "RUN" and tipos[7002] == "STRENGTH"
        # reimportar NÃO duplica (idempotência por strava_activity_id)
        r2 = imp.import_history(uid)
        assert r2["imported"] == 0 and r2["skipped"] == 2
    finally:
        con.execute("DELETE FROM dim_activities WHERE strava_activity_id IN (7001, 7002)")
        con.execute("DELETE FROM strava_tokens WHERE user_id=?", [uid])


def test_import_renova_token_expirado():
    con = get_connection()
    uid = str(uuid4())
    _seed_token(con, uid, expires_in=-10)   # já expirado
    client = _FakeStravaClient(activities=[])
    try:
        StravaImporter(client).import_history(uid)
        assert client.refreshed is True     # renovou antes de chamar a API
    finally:
        con.execute("DELETE FROM strava_tokens WHERE user_id=?", [uid])


def test_callback_enfileira_import_sem_bloquear():
    """O controller do callback SÓ enfileira o import (a API não sabe quem processa)."""
    con = get_connection()
    enqueued = []

    class _RecQueue(JobQueue):
        def start(self): ...
        def enqueue(self, fn, *args, **kwargs): enqueued.append((fn, args))

    client = TestClient(app)
    app.dependency_overrides[get_strava_client] = lambda: _FakeStravaClient(athlete_id=5552)
    app.dependency_overrides[get_job_queue] = lambda: _RecQueue()
    app.dependency_overrides[get_strava_importer] = lambda: StravaImporter(_FakeStravaClient(athlete_id=5552))
    try:
        r = client.get("/api/v1/auth/strava/callback?code=abc", follow_redirects=False)
        assert r.status_code in (302, 307)
        assert "strava_token=" in r.headers["location"]     # loga e redireciona
        assert enqueued and enqueued[0][0].__name__ == "import_history"  # enfileirou o import
    finally:
        app.dependency_overrides.clear()
        con.execute("DELETE FROM strava_tokens WHERE athlete_id=5552")
        con.execute("DELETE FROM auth_users WHERE strava_athlete_id=5552")
