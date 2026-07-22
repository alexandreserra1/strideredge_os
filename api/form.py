"""api/form.py — análise de forma: vídeo -> stride-vision (Rust) -> métricas.

Desenho: Python só ORQUESTRA (constituição §1) — todo o cálculo pesado (pose,
FFT, métricas) roda no binário Rust via subprocess. O vídeo fica no filesystem
(storage/videos/{id}/); o banco guarda caminho + métricas JSON.

Processamento é em BACKGROUND (fila de jobs): o upload responde 'processing' na hora
e um worker roda o motor depois. A conexão DuckDB é thread-safe por cursor (core/database).
"""

import json
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from core.database import get_connection, PROJECT_ROOT
from core.jobs import JobQueue
from core.logging import Logger

VIDEOS_DIR = PROJECT_ROOT / "storage" / "videos"
BINARY = PROJECT_ROOT / "stride_vision" / "target" / "release" / "stride-vision"
MODEL = PROJECT_ROOT / "stride_vision" / "models" / "yolo11n-pose.onnx"

_log = Logger("form")

# Tentativas de processamento antes de marcar 'failed' (1 original + 2 retries). Falha transitória
# passa; falha determinística (vídeo corrompido) esgota rápido e falha honesto.
_MAX_ATTEMPTS = 3

# Métricas do plano frontal — SÓ o motor com --view frontal as mede (queda pélvica + valgo).
_FRONTAL_METRICS = ("pelvic_drop_deg", "knee_valgus_deg")


def fuse_metrics(lateral: dict, frontal: Optional[dict]) -> dict:
    """Funde as métricas dos dois planos numa análise só. Fusão explícita e HONESTA:
      - o lateral é a BASE (cadência, oscilação, tronco, contato, pisada);
      - do frontal só entram pelvic_drop_deg/knee_valgus_deg, e SÓ se a captura frontal for
        `reliable` — se o frontal for ruim, esses fatores ficam None (não chuta) + nota pra refilmar.
    `metric_sources` registra de onde veio cada família (observabilidade)."""
    fused = dict(lateral)
    sources = {"sagittal": "lateral"}
    if frontal is None:
        fused["metric_sources"] = sources
        return fused
    if frontal.get("reliable"):
        for k in _FRONTAL_METRICS:
            fused[k] = frontal.get(k)
        sources["frontal_plane"] = "frontal"
    else:
        for k in _FRONTAL_METRICS:
            fused[k] = None
        sources["frontal_plane"] = "dropped_unreliable"
        reason = frontal.get("reason") or frontal.get("quality_note") or "captura ruim"
        fused["frontal_note"] = (
            f"A captura frontal não ficou confiável ({reason}) — refilme de frente para medir "
            "queda pélvica e valgo dinâmico de joelho.")
    fused["metric_sources"] = sources
    return fused


class FormService:
    """Ciclo de vida de uma análise de forma (criar -> processar -> consultar).

    COMPÕE uma JobQueue (injetada): `create` só ENFILEIRA o processamento e responde
    na hora; um worker roda `_process` depois. A API não sabe quem processa."""

    def __init__(self, queue: JobQueue, binary: Path = BINARY, model: Path = MODEL):
        self.queue = queue
        self.binary = binary
        self.model = model

    # ---------- escrita ----------

    def create(self, video_bytes: bytes, filename: str, activity_id: Optional[str] = None,
               modality: str = "run", view: str = "lateral", user_id: Optional[str] = None,
               frontal_bytes: Optional[bytes] = None, frontal_filename: str = "frontal.mp4") -> dict:
        """Salva o upload, registra a análise e ENFILEIRA o processamento (background).
        Responde na hora com 'processing' — o usuário pode fechar a página e voltar depois.
        `view` = 'lateral' (métricas sagitais) ou 'frontal' (queda pélvica, valgo de joelho).
        `frontal_bytes` (opcional): SEGUNDO clipe, filmado de frente. Quando vem, a análise funde
        os dois planos — o `view` primário (lateral) dá as métricas sagitais e o frontal adiciona
        queda pélvica/valgo. Sem ele o comportamento é idêntico ao de hoje (retrocompatível).
        `user_id` (do token, opcional): liga a análise ao atleta pra correlação com lesão (o
        convidado fica NULL e não entra no dataset)."""
        analysis_id = str(uuid.uuid4())
        adir = VIDEOS_DIR / analysis_id
        adir.mkdir(parents=True, exist_ok=True)
        ext = (filename.rsplit(".", 1)[-1] or "mp4").lower()
        original = adir / f"original.{ext}"
        original.write_bytes(video_bytes)

        view = view if view in ("lateral", "frontal") else "lateral"
        frontal_original = None
        if frontal_bytes:
            fext = (frontal_filename.rsplit(".", 1)[-1] or "mp4").lower()
            frontal_original = adir / f"original_frontal.{fext}"
            frontal_original.write_bytes(frontal_bytes)
            view = "combined"   # dois planos fundidos numa análise só (observabilidade)
        get_connection().execute(
            "INSERT INTO form_analyses (analysis_id, activity_id, status, modality, view, user_id) "
            "VALUES (?, ?, 'processing', ?, ?, ?)",
            [analysis_id, activity_id, modality, view, user_id])
        self.queue.enqueue(self._process, analysis_id, original, view, frontal_original)
        return {"analysis_id": analysis_id, "status": "processing"}

    # PATH com ffmpeg (Homebrew no macOS) pro subprocess do motor/normalização.
    _ENV = {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"}

    # Ladder de normalização: QUALQUER vídeo (qualquer container/codec/rotação/bit-depth) vira um
    # h264 8-bit upright que o motor lê. Cada degrau comprime mais e é mais compatível/rápido que o
    # anterior — se um encode falha (formato exótico, arquivo grande, timeout), desce um degrau.
    _NORMALIZE_LADDER = (
        {"max_side": 1280, "crf": "23", "preset": "medium"},    # padrão: boa qualidade
        {"max_side": 960, "crf": "28", "preset": "veryfast"},   # fallback: menor + mais rápido
        {"max_side": 640, "crf": "30", "preset": "ultrafast"},  # último recurso: máx. compatibilidade
    )

    def _normalize(self, src: Path) -> Path:
        """Prepara QUALQUER vídeo pro motor. ASSA a rotação (o ffmpeg auto-rotaciona no decode; o
        buffer cru do motor NÃO, então celular gravado em pé sai deitado e o motor não detecta
        ninguém) e força h264 + yuv420p 8-bit (assim lê HEVC/VP9/10-bit/HDR também), limitando o
        lado maior e garantindo dimensões pares. Desce a `_NORMALIZE_LADDER` (comprime mais a cada
        degrau) se um encode falhar; só devolve o original se TODOS falharem."""
        dst = src.parent / f"{src.stem}.normalized.mp4"   # único por clipe (lateral × frontal)
        for step in self._NORMALIZE_LADDER:
            if self._ffmpeg_normalize(src, dst, **step):
                return dst
        return src

    def _ffmpeg_normalize(self, src: Path, dst: Path, max_side: int, crf: str, preset: str) -> bool:
        """Um degrau da ladder: transcodifica pra h264 yuv420p upright. True se gerou arquivo válido."""
        vf = (f"scale='min({max_side},iw)':'min({max_side},ih)':force_original_aspect_ratio=decrease,"
              "scale=trunc(iw/2)*2:trunc(ih/2)*2")
        cmd = [
            "ffmpeg", "-v", "error", "-y", "-i", str(src),
            "-vf", vf, "-metadata:s:v:0", "rotate=0", "-c:v", "libx264",
            "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", "-an", str(dst),
        ]
        r = subprocess.run(cmd, env={**self._ENV}, capture_output=True, text=True, timeout=300)
        return r.returncode == 0 and dst.exists() and dst.stat().st_size > 0

    def _run_engine(self, original: Path, overlay: Path, view: str) -> dict:
        """Normaliza UM clipe e roda o motor Rust nele. Devolve as métricas (dict). Pesado —
        cada clipe (lateral/frontal) passa por aqui separado, com seu próprio --view."""
        source = self._normalize(original)   # celular -> vídeo limpo (rotação assada)
        result = subprocess.run(
            [str(self.binary), str(source), str(overlay), "--view", view],
            env={"STRIDE_MODEL": str(self.model), **self._ENV},
            capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[-300:] or "motor falhou")
        metrics = json.loads((overlay.parent / f"{overlay.stem}.metrics.json").read_text())
        if source != original:
            source.unlink(missing_ok=True)   # normalizado é descartável (só o motor precisava)
        return metrics

    def _process(self, analysis_id: str, original: Path, view: str = "lateral",
                 frontal_original: Optional[Path] = None, attempt: int = 1) -> None:
        """Roda o motor Rust (um clipe, ou lateral+frontal fundidos); grava métricas ou o erro.
        (thread própria + cursor próprio)"""
        overlay = original.parent / "overlay.mp4"
        con = get_connection()
        try:
            base = self._run_engine(original, overlay, view)
            frontal = None
            if frontal_original is not None:
                frontal = self._run_engine(
                    frontal_original, original.parent / "overlay_frontal.mp4", "frontal")
            metrics = fuse_metrics(base, frontal) if frontal_original is not None else base
            stored_view = "combined" if frontal_original is not None else view
            con.execute(
                "UPDATE form_analyses SET status='done', video_path=?, metrics=?, view=? "
                "WHERE analysis_id=?", [str(overlay), json.dumps(metrics), stored_view, analysis_id])
            original.unlink(missing_ok=True)   # original descartado: métricas + overlay bastam
            if frontal_original is not None:
                frontal_original.unlink(missing_ok=True)
            # Observabilidade do quality gate: loga os INSUMOS da decisão de confiabilidade, pra
            # calibrar o limiar com dado real (agregar por `reason`) em vez de no chute.
            _log.info("form_done", analysis_id=analysis_id, reliable=base.get("reliable"),
                      reason=base.get("reason"), detection_rate=base.get("detection_rate_pct"),
                      raw_vert_osc_pct=base.get("diag_vert_osc_pct"),
                      leg_len_px=base.get("diag_leg_len_px"), view=stored_view,
                      frontal_reliable=(frontal or {}).get("reliable") if frontal else None)
        except Exception as e:  # noqa: BLE001 — qualquer falha vira retry ou status 'failed'
            # Retry com re-enfileiramento: falha transitória (timeout sob carga, glitch do ffmpeg)
            # costuma passar na 2ª. Re-enfileira até _MAX_ATTEMPTS mantendo 'processing'; só marca
            # 'failed' ao esgotar. O original só é apagado no SUCESSO, então o arquivo existe p/ retry.
            if attempt < _MAX_ATTEMPTS and original.exists():
                _log.info("form_retry", analysis_id=analysis_id, attempt=attempt,
                          error=str(e)[:200])
                self.queue.enqueue(self._process, analysis_id, original, view,
                                   frontal_original, attempt + 1)
                return
            con.execute(
                "UPDATE form_analyses SET status='failed', error=? WHERE analysis_id=?",
                [str(e)[:300], analysis_id])
            _log.error("form_failed", analysis_id=analysis_id, attempts=attempt, error=str(e)[:200])

    # ---------- leitura ----------

    _COLS = ("analysis_id, activity_id, status, video_path, metrics, error, created_at, "
             "modality, view")

    def get(self, analysis_id: str) -> Optional[dict]:
        row = get_connection().execute(
            f"SELECT {self._COLS} FROM form_analyses WHERE analysis_id = ?",
            [analysis_id]).fetchone()
        return self._row(row) if row else None

    def list(self, activity_id: Optional[str] = None) -> list:
        sql = f"SELECT {self._COLS} FROM form_analyses"
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
            "modality": r[7] if len(r) > 7 else "run",
            "view": r[8] if len(r) > 8 else "lateral",
        }


def recover_orphaned_analyses() -> int:
    """Recuperação de crash: análises que ficaram 'processing' (o servidor caiu/reiniciou
    no meio do job, então o worker morreu sem terminar) viram 'failed' com aviso pra
    reenviar. Rodado no boot da API. Devolve quantas foram recuperadas.

    (Re-enfileirar o original em vez de falhar é enhancement futuro: o original só é apagado
    no sucesso, então o arquivo ainda existe — mas falhar-e-avisar é o comportamento honesto
    e simples pra v1.)"""
    con = get_connection()
    n = con.execute("SELECT COUNT(*) FROM form_analyses WHERE status = 'processing'").fetchone()[0]
    if n:
        con.execute(
            "UPDATE form_analyses SET status = 'failed', "
            "error = 'Interrompido por reinício do servidor — reenvie o vídeo.' "
            "WHERE status = 'processing'")
        _log.info("orphans_recovered", count=n)
    return n
