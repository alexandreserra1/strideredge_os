"""ingestion/garmin_sync.py — automação da ingestão (Peça 4).

Loga na conta Garmin, lista atividades novas e baixa o .FIT ORIGINAL, jogando no
ingest_fit_file (idempotente). Sync INCREMENTAL: só processa o que ainda não foi
ingerido (compara garmin_activity_id com o que já está no DuckDB).

Desenho OOP: GarminSync COMPÕE um cliente (injetável → testável com fake) e a
função de ingestão. O login real (garth, com cache de token) fica no factory.
"""

import io
import os
import tempfile
import zipfile
from pathlib import Path

from core.database import PROJECT_ROOT, get_connection
from core.ingest import ingest_fit_file

# Diretório onde o garth cacheia o token de sessão (login uma vez, reusa depois).
TOKEN_DIR = str(Path.home() / ".garminconnect")


def _load_dotenv() -> None:
    """Carrega .env (KEY=VALUE) pro ambiente, sem dependência externa. Gitignored."""
    env = PROJECT_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))


class GarminSync:
    """Orquestra o sync incremental de atividades da Garmin."""

    def __init__(self, client, user_id: str, device_id: int, ingest=ingest_fit_file):
        self.client = client          # objeto garminconnect.Garmin (ou fake nos testes)
        self.user_id = user_id
        self.device_id = device_id
        self.ingest = ingest

    def existing_garmin_ids(self) -> set:
        con = get_connection()
        rows = con.execute(
            "SELECT garmin_activity_id FROM dim_activities WHERE garmin_activity_id IS NOT NULL"
        ).fetchall()
        return {r[0] for r in rows}

    def _extract_fit(self, zip_bytes: bytes) -> str:
        """O download ORIGINAL vem como ZIP com o .FIT dentro — extrai pra um temp."""
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            fit_name = next(n for n in zf.namelist() if n.lower().endswith(".fit"))
            data = zf.read(fit_name)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".fit")
        tmp.write(data)
        tmp.close()
        return tmp.name

    def _process_activity(self, garmin_id: int, name: str) -> dict:
        """Baixa o .FIT ORIGINAL e ingere. (Não testado em unit — usa rede/garmin.)"""
        from garminconnect import Garmin
        zip_bytes = self.client.download_activity(
            garmin_id, dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL
        )
        fit_path = self._extract_fit(zip_bytes)
        try:
            return self.ingest(
                file_path=fit_path, garmin_activity_id=garmin_id,
                user_id=self.user_id, device_id=self.device_id, activity_name=name,
            )
        finally:
            os.unlink(fit_path)

    def sync(self, start: str, end: str) -> dict:
        """Sincroniza atividades no intervalo [start, end] (YYYY-MM-DD)."""
        existing = self.existing_garmin_ids()
        activities = self.client.get_activities_by_date(start, end)
        new = [a for a in activities if a["activityId"] not in existing]
        imported, errors = 0, []
        for a in new:
            try:
                res = self._process_activity(a["activityId"], a.get("activityName", "Atividade Garmin"))
                if res.get("status") == "imported":
                    imported += 1
            except Exception as e:  # uma atividade ruim nao aborta as demais
                errors.append({"activityId": a["activityId"], "erro": str(e).splitlines()[0]})
        return {"total": len(activities), "new": len(new), "imported": imported, "errors": errors}


def connect_garmin(email: str = None, password: str = None):
    """Cria e loga um cliente Garmin. Reusa o token cacheado se existir (sem re-login).

    Credenciais: passe email/senha OU defina GARMIN_EMAIL / GARMIN_PASSWORD no ambiente.
    Na 1a vez (ou com MFA) faz login completo; depois o garth reusa o token de TOKEN_DIR.
    """
    from garminconnect import Garmin

    _load_dotenv()
    email = email or os.environ.get("GARMIN_EMAIL")
    password = password or os.environ.get("GARMIN_PASSWORD")
    try:
        client = Garmin()
        client.login(TOKEN_DIR)  # reusa token cacheado
    except Exception:
        client = Garmin(email, password)
        client.login()
        client.garth.dump(TOKEN_DIR)  # cacheia pra próxima
    return client


if __name__ == "__main__":
    import sys
    from datetime import date, timedelta
    from core.seed import SEED_USER_ID, SEED_DEVICE_ID

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    start = (date.today() - timedelta(days=days)).isoformat()
    end = date.today().isoformat()
    print(f"Sincronizando atividades de {start} a {end}...")
    client = connect_garmin()  # usa GARMIN_EMAIL / GARMIN_PASSWORD do ambiente
    sync = GarminSync(client=client, user_id=SEED_USER_ID, device_id=SEED_DEVICE_ID)
    result = sync.sync(start, end)
    print(result)
    if result["imported"]:
        from analytics.training_load import refresh_summary_cache
        refresh_summary_cache()  # atualiza agregados pros novos treinos
        print("Cache de resumo atualizado.")
