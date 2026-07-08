"""api/form.py — análise de forma: vídeo -> stride-vision (Rust) -> métricas.

Desenho: Python só ORQUESTRA (constituição §1) — todo o cálculo pesado (pose,
FFT, métricas) roda no binário Rust via subprocess. O vídeo fica no filesystem
(storage/videos/{id}/); o banco guarda caminho + métricas JSON.

Processamento é assíncrono (thread): um vídeo de 30s leva ~1min em CPU.
A conexão DuckDB é thread-safe por cursor (core/database).
"""

import json
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Optional

from core.database import get_connection, PROJECT_ROOT
from core.logging import Logger

VIDEOS_DIR = PROJECT_ROOT / "storage" / "videos"
BINARY = PROJECT_ROOT / "stride_vision" / "target" / "release" / "stride-vision"
MODEL = PROJECT_ROOT / "stride_vision" / "models" / "yolo11n-pose.onnx"

_log = Logger("form")


class FormService:
    """Ciclo de vida de uma análise de forma (criar -> processar -> consultar)."""

    def __init__(self, binary: Path = BINARY, model: Path = MODEL):
        self.binary = binary
        self.model = model

    # ---------- escrita ----------

    def create(self, video_bytes: bytes, filename: str,
               activity_id: Optional[str] = None) -> dict:
        """Salva o upload, registra a análise e dispara o processamento em background."""
        analysis_id = str(uuid.uuid4())
        adir = VIDEOS_DIR / analysis_id
        adir.mkdir(parents=True, exist_ok=True)
        ext = (filename.rsplit(".", 1)[-1] or "mp4").lower()
        original = adir / f"original.{ext}"
        original.write_bytes(video_bytes)

        get_connection().execute(
            "INSERT INTO form_analyses (analysis_id, activity_id, status) VALUES (?, ?, 'processing')",
            [analysis_id, activity_id])
        threading.Thread(target=self._process, args=(analysis_id, original),
                         daemon=True).start()
        return {"analysis_id": analysis_id, "status": "processing"}

    def _process(self, analysis_id: str, original: Path) -> None:
        """Roda o motor Rust; grava métricas ou o erro. (thread própria + cursor próprio)"""
        overlay = original.parent / "overlay.mp4"
        con = get_connection()
        try:
            result = subprocess.run(
                [str(self.binary), str(original), str(overlay)],
                env={"STRIDE_MODEL": str(self.model), "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
                capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip()[-300:] or "motor falhou")
            metrics = (original.parent / "overlay.metrics.json").read_text()
            con.execute(
                "UPDATE form_analyses SET status='done', video_path=?, metrics=? WHERE analysis_id=?",
                [str(overlay), metrics, analysis_id])
            original.unlink(missing_ok=True)   # original descartado: métricas + overlay bastam
            _log.info("form_done", analysis_id=analysis_id)
        except Exception as e:  # noqa: BLE001 — qualquer falha vira status 'failed'
            con.execute(
                "UPDATE form_analyses SET status='failed', error=? WHERE analysis_id=?",
                [str(e)[:300], analysis_id])
            _log.error("form_failed", analysis_id=analysis_id, error=str(e)[:200])

    # ---------- leitura ----------

    def get(self, analysis_id: str) -> Optional[dict]:
        row = get_connection().execute(
            """SELECT analysis_id, activity_id, status, video_path, metrics, error, created_at
               FROM form_analyses WHERE analysis_id = ?""", [analysis_id]).fetchone()
        return self._row(row) if row else None

    def list(self, activity_id: Optional[str] = None) -> list:
        sql = """SELECT analysis_id, activity_id, status, video_path, metrics, error, created_at
                 FROM form_analyses"""
        args = []
        if activity_id:
            sql += " WHERE activity_id = ?"
            args.append(activity_id)
        rows = get_connection().execute(sql + " ORDER BY created_at DESC", args).fetchall()
        return [self._row(r) for r in rows]

    def video_path(self, analysis_id: str) -> Optional[str]:
        row = self.get(analysis_id)
        return row["video_path"] if row and row.get("video_path") else None

    @staticmethod
    def _row(r) -> dict:
        return {
            "analysis_id": str(r[0]),
            "activity_id": str(r[1]) if r[1] else None,
            "status": r[2],
            "video_path": r[3],
            "metrics": json.loads(r[4]) if r[4] else None,
            "error": r[5],
            "created_at": str(r[6]),
        }
