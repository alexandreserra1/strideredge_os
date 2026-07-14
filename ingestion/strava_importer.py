"""ingestion/strava_importer.py — login + import de histórico via Strava (API oficial).

Duas peças (composição, testáveis sem rede):
  - StravaClient: fala com a API do Strava (OAuth + atividades). HTTP injetável → fake nos testes.
  - StravaImporter (BaseActivityImporter): usa o token guardado, puxa o histórico, mapeia o tipo
    de esporte pro nosso primary_type e faz upsert idempotente em dim_activities.

Por que Strava e não Garmin pro multiusuário: OAuth oficial (sem senha por usuário), import no
login e webhook de treino novo. O .FIT upload continua como caminho de fidelidade (o Strava
descarta as running dynamics avançadas). Ver plan.md §1.2.
"""

import os
import time
from typing import Optional
from urllib.parse import urlencode
from uuid import uuid4

import httpx

from core.database import get_connection
from core.framework.interfaces import BaseActivityImporter
from core.logging import Logger

_log = Logger("strava")

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
API = "https://www.strava.com/api/v3"

# Strava sport_type -> nosso primary_type (dim_activities). Corrida/HIIT/força/cardio.
_TYPE_MAP = {
    "Run": "RUN", "TrailRun": "RUN", "VirtualRun": "RUN",
    "Workout": "HIIT", "HighIntensityIntervalTraining": "HIIT", "Crossfit": "HIIT",
    "WeightTraining": "STRENGTH",
    "Ride": "CARDIO", "VirtualRide": "CARDIO", "Elliptical": "CARDIO", "Rowing": "CARDIO",
}


def _primary_type(sport_type: str) -> str:
    return _TYPE_MAP.get(sport_type, "OTHER")


class StravaClient:
    """Cliente da API do Strava (OAuth + atividades). HTTP injetável (fake nos testes)."""

    def __init__(self, client_id: str = None, client_secret: str = None, http=None):
        self.client_id = client_id or os.environ.get("STRAVA_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("STRAVA_CLIENT_SECRET")
        self._http = http or httpx.Client(timeout=30.0)

    def authorize_url(self, redirect_uri: str, state: str = "") -> str:
        """URL pra onde o usuário é mandado autorizar (scope de leitura de atividades)."""
        params = urlencode({
            "client_id": self.client_id, "redirect_uri": redirect_uri,
            "response_type": "code", "approval_prompt": "auto",
            "scope": "activity:read_all", "state": state,
        })
        return f"{AUTHORIZE_URL}?{params}"

    def exchange_code(self, code: str) -> dict:
        """Troca o authorization_code por tokens + resumo do atleta."""
        r = self._http.post(TOKEN_URL, data={
            "client_id": self.client_id, "client_secret": self.client_secret,
            "code": code, "grant_type": "authorization_code",
        })
        r.raise_for_status()
        return r.json()

    def refresh(self, refresh_token: str) -> dict:
        """Renova o access_token expirado."""
        r = self._http.post(TOKEN_URL, data={
            "client_id": self.client_id, "client_secret": self.client_secret,
            "refresh_token": refresh_token, "grant_type": "refresh_token",
        })
        r.raise_for_status()
        return r.json()

    def get_activities(self, access_token: str, page: int = 1, per_page: int = 100) -> list:
        r = self._http.get(f"{API}/athlete/activities",
                           headers={"Authorization": f"Bearer {access_token}"},
                           params={"page": page, "per_page": per_page})
        r.raise_for_status()
        return r.json()


class StravaImporter(BaseActivityImporter):
    """Importa o histórico do Strava pro dim_activities. COMPÕE um StravaClient + o user_id.

    Idempotente por strava_activity_id (índice único): reimportar não duplica. Renova o token
    quando expirado. Roda no worker da fila (import_history)."""

    def __init__(self, client: StravaClient):
        self.client = client

    def _valid_token(self, user_id: str) -> Optional[str]:
        """Access token válido do usuário (renova se expirou). None se não há vínculo."""
        con = get_connection()
        row = con.execute(
            "SELECT access_token, refresh_token, epoch(expires_at) FROM strava_tokens WHERE user_id = ?",
            [user_id]).fetchone()
        if not row:
            return None
        access, refresh, exp = row
        if exp and exp <= time.time() + 60:            # expira em <1min -> renova
            data = self.client.refresh(refresh)
            access = data["access_token"]
            con.execute(
                "UPDATE strava_tokens SET access_token=?, refresh_token=?, "
                "expires_at=to_timestamp(?), updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                [access, data["refresh_token"], data["expires_at"], user_id])
        return access

    def import_history(self, user_id: str, max_pages: int = 5) -> dict:
        """Puxa o histórico (paginado) e faz upsert idempotente. Resumo {imported, skipped}."""
        access = self._valid_token(user_id)
        if not access:
            return {"imported": 0, "skipped": 0, "errors": ["sem token Strava"]}
        con = get_connection()
        device_id = self._default_device()
        imported, skipped = 0, 0
        for page in range(1, max_pages + 1):
            acts = self.client.get_activities(access, page=page)
            if not acts:
                break
            for a in acts:
                sid = a["id"]
                if con.execute("SELECT 1 FROM dim_activities WHERE strava_activity_id = ?",
                               [sid]).fetchone():
                    skipped += 1
                    continue
                con.execute(
                    "INSERT INTO dim_activities (activity_id, strava_activity_id, activity_name, "
                    "start_time, total_distance_meters, total_duration_seconds, primary_type) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [str(uuid4()), sid, a.get("name", "Treino Strava"),
                     a.get("start_date"), a.get("distance"), a.get("elapsed_time"),
                     _primary_type(a.get("sport_type") or a.get("type", ""))])
                imported += 1
        _log.info("strava_import_done", user_id=user_id, imported=imported, skipped=skipped)
        return {"imported": imported, "skipped": skipped, "errors": []}

    @staticmethod
    def _default_device() -> Optional[int]:
        row = get_connection().execute("SELECT device_id FROM dim_devices LIMIT 1").fetchone()
        return row[0] if row else None
