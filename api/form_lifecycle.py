"""Manutenção de análises de forma que roda no boot, fora do serviço HTTP."""

import shutil
from datetime import datetime
from pathlib import Path

from core.database import PROJECT_ROOT, get_connection
from core.logging import Logger


VIDEOS_DIR = PROJECT_ROOT / "storage" / "videos"
_log = Logger("form")


def recover_orphaned_analyses() -> int:
    """Marca jobs interrompidos por reinício como falhos, sem alegar conclusão."""
    con = get_connection()
    count = con.execute("SELECT COUNT(*) FROM form_analyses WHERE status = 'processing'").fetchone()[0]
    if count:
        con.execute(
            "UPDATE form_analyses SET status = 'failed', "
            "error = 'Interrompido por reinício do servidor — reenvie o vídeo.' "
            "WHERE status = 'processing'")
        _log.info("orphans_recovered", count=count)
    return count


def purge_expired_guest_analyses() -> int:
    """Apaga capacidades expiradas e seus vídeos; os IDs vêm exclusivamente do banco."""
    con = get_connection()
    rows = con.execute(
        "SELECT analysis_id FROM form_analyses WHERE user_id IS NULL "
        "AND access_token_expires_at IS NOT NULL AND access_token_expires_at <= ?",
        [datetime.utcnow()]).fetchall()
    for (analysis_id,) in rows:
        shutil.rmtree(VIDEOS_DIR / str(analysis_id), ignore_errors=True)
    if rows:
        con.execute(
            "DELETE FROM form_analyses WHERE user_id IS NULL "
            "AND access_token_expires_at IS NOT NULL AND access_token_expires_at <= ?",
            [datetime.utcnow()])
        _log.info("expired_guest_analyses_purged", count=len(rows))
    return len(rows)
