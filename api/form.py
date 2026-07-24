"""Fachada de ciclo de vida da análise de forma.

Python só orquestra: a execução pesada vive em ``form_processing`` e o motor de visão em Rust.
Este módulo conserva o contrato usado pela API: criar, consultar e autorizar análises.
"""

import hashlib
import hmac
import json
import secrets
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from api.form_processing import FormProcessingMixin, _MAX_ATTEMPTS
from api.form_lifecycle import purge_expired_guest_analyses, recover_orphaned_analyses
from api.pose_backends import (BackendConfigurationError, PoseBackendResolver,
                               PoseBackendSnapshot, ServerPoseBackendResolver)
from core.config import pose_backend, pose_shadow_backend, validate_pose_backend
from core.database import PROJECT_ROOT, get_connection
from core.jobs import JobQueue


VIDEOS_DIR = PROJECT_ROOT / "storage" / "videos"
BINARY = PROJECT_ROOT / "stride_vision" / "target" / "release" / "stride-vision"
MODEL = PROJECT_ROOT / "stride_vision" / "models" / "yolo11n-pose.onnx"
_VIDEO_EXTENSIONS = {"mp4", "mov", "m4v", "avi", "webm", "mkv"}
_GUEST_ACCESS_TTL = timedelta(days=7)


class QueueFullError(RuntimeError):
    """O processamento pesado está no limite; o upload não deve ficar retido sem prazo."""


class FormService(FormProcessingMixin):
    """Fachada estável: cria, autoriza e consulta análises; o mixin executa os jobs pesados."""

    _COLS = ("analysis_id, activity_id, status, video_path, metrics, error, created_at, "
             "modality, view, user_id, access_token_hash, access_token_expires_at, "
             "backend_requested, backend_effective, model_version, model_assets")
    # Shadow é telemetria de transição: o produto mede com BlazePose, e YOLO só observa a mesma
    # captura. Halpe26 não entra porque seus pesos não estão aprovados para produto.
    _ALLOWED_SHADOW_PAIRS = {"blazepose33": "yolo17"}

    def __init__(self, queue: JobQueue, binary: Path = BINARY, model: Path = MODEL,
                 backend: Optional[str] = None,
                 backend_resolver: Optional[PoseBackendResolver] = None,
                 shadow_backend: Optional[str] = None):
        self.queue = queue
        self.binary = binary
        self.model = model
        try:
            self.backend = pose_backend() if backend is None else validate_pose_backend(backend)
        except ValueError as exc:
            raise BackendConfigurationError("Backend de pose não permitido.") from exc
        self.backend_resolver = backend_resolver or ServerPoseBackendResolver(model)
        self.shadow_backend = None
        self._shadow_configuration_error = None
        try:
            configured_shadow = pose_shadow_backend() if shadow_backend is None else (
                validate_pose_backend(shadow_backend) if shadow_backend else None)
            if configured_shadow is not None:
                if self._ALLOWED_SHADOW_PAIRS.get(self.backend) != configured_shadow:
                    raise ValueError("combinação de shadow não suportada")
                self.shadow_backend = configured_shadow
        except ValueError:
            self._shadow_configuration_error = "invalid_server_configuration"

    def _resolve_backend_snapshot(self, backend: str) -> PoseBackendSnapshot:
        """Resolve um backend server-side sem aceitar dados livres do request."""
        try:
            snapshot = self.backend_resolver.resolve(backend)
        except BackendConfigurationError:
            raise
        except (ValueError, OSError) as exc:
            raise BackendConfigurationError("Assets do motor indisponíveis no servidor.") from exc
        if snapshot.requested != backend or snapshot.effective not in ("yolo17", "halpe26", "blazepose33"):
            raise BackendConfigurationError("Resposta inválida do registro de assets.")
        expected_env = {
            "yolo17": {"STRIDE_MODEL"},
            "halpe26": {"STRIDE_HALPE_DETECTOR", "STRIDE_HALPE_POSE"},
            "blazepose33": {"STRIDE_MEDIAPIPE_LIB", "STRIDE_BLAZEPOSE_MODEL"},
        }[snapshot.effective]
        if set(snapshot.subprocess_env) != expected_env:
            raise BackendConfigurationError("Resposta inválida do registro de assets.")
        if not all(isinstance(path, str) and Path(path).is_absolute()
                   for path in snapshot.subprocess_env.values()):
            raise BackendConfigurationError("Resposta inválida do registro de assets.")
        try:
            json.dumps(snapshot.model_assets, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise BackendConfigurationError("Resposta inválida do registro de assets.") from exc
        return snapshot

    def _backend_snapshot(self) -> PoseBackendSnapshot:
        return self._resolve_backend_snapshot(self.backend)

    def create(self, video_bytes: bytes, filename: str, activity_id: Optional[str] = None,
               modality: str = "run", view: str = "lateral", user_id: Optional[str] = None,
               frontal_bytes: Optional[bytes] = None, frontal_filename: str = "frontal.mp4") -> dict:
        """Persiste o upload e enfileira o processamento, sem executá-lo no request."""
        snapshot = self._backend_snapshot()
        analysis_id, adir = self._new_analysis_dir()
        original = adir / f"original.{self._extension(filename)}"
        original.write_bytes(video_bytes)
        frontal_original = None
        if frontal_bytes:
            frontal_original = adir / f"original_frontal.{self._extension(frontal_filename)}"
            frontal_original.write_bytes(frontal_bytes)
        return self._register_and_enqueue(
            analysis_id, adir, original, activity_id, modality, view, user_id, frontal_original,
            snapshot)

    def create_from_staged(self, video_path: Path, filename: str,
                           activity_id: Optional[str] = None, modality: str = "run",
                           view: str = "lateral", user_id: Optional[str] = None,
                           frontal_path: Optional[Path] = None,
                           frontal_filename: str = "frontal.mp4") -> dict:
        """Promove arquivos já copiados por chunks, sem rematerializá-los em RAM."""
        snapshot = self._backend_snapshot()
        analysis_id, adir = self._new_analysis_dir()
        original = adir / f"original.{self._extension(filename)}"
        frontal_original = None
        try:
            shutil.move(str(video_path), str(original))
            if frontal_path is not None:
                frontal_original = adir / f"original_frontal.{self._extension(frontal_filename)}"
                shutil.move(str(frontal_path), str(frontal_original))
            return self._register_and_enqueue(
                analysis_id, adir, original, activity_id, modality, view, user_id, frontal_original,
                snapshot)
        except Exception:
            self._discard_dir(adir)
            raise

    @staticmethod
    def _extension(filename: str) -> str:
        ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
        return ext if ext in _VIDEO_EXTENSIONS else "mp4"

    @staticmethod
    def _discard_dir(adir: Path) -> None:
        if adir.exists():
            shutil.rmtree(adir)

    @staticmethod
    def _new_analysis_dir() -> tuple:
        analysis_id = str(uuid.uuid4())
        adir = VIDEOS_DIR / analysis_id
        adir.mkdir(parents=True, exist_ok=False)
        return analysis_id, adir

    def _register_and_enqueue(self, analysis_id: str, adir: Path, original: Path,
                              activity_id: Optional[str], modality: str, view: str,
                              user_id: Optional[str], frontal_original: Optional[Path],
                              snapshot: PoseBackendSnapshot) -> dict:
        view = view if view in ("lateral", "frontal") else "lateral"
        if frontal_original is not None:
            view = "combined"
        access_token = None
        access_token_hash = None
        access_token_expires_at = None
        if user_id is None:
            access_token = secrets.token_urlsafe(32)
            access_token_hash = hashlib.sha256(access_token.encode()).hexdigest()
            access_token_expires_at = datetime.utcnow() + _GUEST_ACCESS_TTL
        get_connection().execute(
            "INSERT INTO form_analyses "
            "(analysis_id, activity_id, status, modality, view, user_id, access_token_hash, "
            "access_token_expires_at, backend_requested, backend_effective, model_version, "
            "model_assets) VALUES (?, ?, 'processing', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [analysis_id, activity_id, modality, view, user_id, access_token_hash,
             access_token_expires_at, snapshot.requested, snapshot.effective, snapshot.model_version,
             json.dumps(snapshot.model_assets, sort_keys=True)])
        accepted = self.queue.enqueue(
            self._process, analysis_id, original, view, frontal_original, snapshot)
        if accepted is False:
            get_connection().execute("DELETE FROM form_analyses WHERE analysis_id = ?", [analysis_id])
            self._discard_dir(adir)
            raise QueueFullError("Processamento ocupado; tente novamente em alguns minutos.")
        result = {"analysis_id": analysis_id, "status": "processing"}
        if access_token:
            result["access_token"] = access_token
        return result

    def get(self, analysis_id: str) -> Optional[dict]:
        row = get_connection().execute(
            f"SELECT {self._COLS} FROM form_analyses WHERE analysis_id = ?",
            [analysis_id]).fetchone()
        return self._row(row) if row else None

    @staticmethod
    def _has_access(row, requester_user_id: Optional[str], access_token: Optional[str]) -> bool:
        owner, stored_hash, expires_at = row[9], row[10], row[11]
        if requester_user_id and owner and str(owner) == str(requester_user_id):
            return True
        if owner is None and access_token and stored_hash:
            if expires_at and expires_at <= datetime.utcnow():
                return False
            supplied_hash = hashlib.sha256(access_token.encode()).hexdigest()
            return hmac.compare_digest(supplied_hash, stored_hash)
        return False

    def get_authorized(self, analysis_id: str, requester_user_id: Optional[str],
                       access_token: Optional[str]) -> Optional[dict]:
        row = get_connection().execute(
            f"SELECT {self._COLS} FROM form_analyses WHERE analysis_id = ?",
            [analysis_id]).fetchone()
        if not row or not self._has_access(row, requester_user_id, access_token):
            return None
        return self._row(row)

    def list(self, user_id: str, activity_id: Optional[str] = None) -> list:
        sql = f"SELECT {self._COLS} FROM form_analyses WHERE user_id = ?"
        args = [user_id]
        if activity_id:
            sql += " AND activity_id = ?"
            args.append(activity_id)
        rows = get_connection().execute(sql + " ORDER BY created_at DESC", args).fetchall()
        return [self._row(row) for row in rows]

    def authorized_video_path(self, analysis_id: str, requester_user_id: Optional[str],
                              access_token: Optional[str]) -> Optional[str]:
        row = get_connection().execute(
            f"SELECT {self._COLS} FROM form_analyses WHERE analysis_id = ?",
            [analysis_id]).fetchone()
        if not row or not self._has_access(row, requester_user_id, access_token):
            return None
        return row[3] if row[3] else None

    @staticmethod
    def _row(row) -> dict:
        return {
            "analysis_id": str(row[0]),
            "activity_id": str(row[1]) if row[1] else None,
            "status": row[2],
            "metrics": json.loads(row[4]) if row[4] else None,
            "error": row[5],
            "created_at": str(row[6]),
            "modality": row[7] if len(row) > 7 else "run",
            "view": row[8] if len(row) > 8 else "lateral",
            "backend": {
                "requested": row[12] if len(row) > 12 else None,
                "effective": row[13] if len(row) > 13 else None,
                "model_version": row[14] if len(row) > 14 else None,
                "assets": json.loads(row[15]) if len(row) > 15 and row[15] else {},
            },
        }
